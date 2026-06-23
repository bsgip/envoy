import asyncio
import logging
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from envoy.notification.exception import NotificationTransmitError
from envoy.server.api.response import SEP_XML_MIME
from envoy.server.manager.time import utc_now
from envoy.server.model.subscription import NotificationDeadLetter, NotificationTransmit, TransmitNotificationLog

HEADER_SUBSCRIPTION_ID = "x-envoy-subscription-href"
HEADER_NOTIFICATION_ID = "x-envoy-notification-id"
HEADER_CONTENT_TYPE = "Content-Type"

logger = logging.getLogger(__name__)

TRANSMIT_TIMEOUT_SECONDS = 30
RETRY_DELAYS = [timedelta(seconds=10), timedelta(seconds=100), timedelta(seconds=300), timedelta(minutes=30)]

# How far into the future a claimed notification_transmit row has its execute_after pushed while it's being sent. This
# "lease" keeps a row out of the due window for the duration of the (locked) send so a concurrent worker - or this
# worker after a crash mid-send - won't re-grab it until the lease expires. Must exceed TRANSMIT_TIMEOUT_SECONDS.
LEASE_SECONDS = 120


@dataclass(frozen=True, slots=False)
class TransmitResult:
    """Represents a success/error result in transmitting to a remote URI"""

    success: bool
    transmit_start: datetime  # tz aware start of transmission
    transmit_end: datetime  # tz aware end of transmission
    http_status_code: int | None  # Can be None if there was a failure connecting / timeout


@dataclass(frozen=True)
class ClaimedTransmit:
    """An in-memory snapshot of a notification_transmit row claimed for sending (detached from any session)"""

    notification_transmit_id: int
    subscription_id: int
    subscription_href: str
    notification_id: str
    remote_uri: str
    content: str
    attempt: int


def create_transmit_notification_log(
    result: TransmitResult | NotificationTransmitError, attempt: int, subscription_id: int, content: str
) -> TransmitNotificationLog:
    duration_ms = int((result.transmit_end - result.transmit_start).total_seconds() * 1000)
    return TransmitNotificationLog(
        subscription_id_snapshot=subscription_id,
        transmit_time=result.transmit_start,
        transmit_duration_ms=duration_ms,
        notification_size_bytes=len(content),
        attempt=attempt,
        http_status_code=-1 if result.http_status_code is None else result.http_status_code,
    )


def attempt_to_retry_delay(attempt: int) -> timedelta | None:
    """Given the number of attempt just tried - return a delay that should be applied before attempting again (or none
    if no more attempts should be made)"""
    if attempt >= len(RETRY_DELAYS):
        return None

    return RETRY_DELAYS[attempt]


async def do_transmit_notification(
    remote_uri: str,
    content: str,
    subscription_href: str,
    notification_id: str,
    attempt: int,
    verify: ssl.SSLContext | bool = True,
) -> TransmitResult:
    """Internal method for transmitting the notification - Raises a NotificationTransmitError if the request fails and
    needs retrying otherwise returns TransmitResult indicating the final result.

    verify: The httpx "verify" argument (bool toggle or a prebuilt mTLS SSLContext) - see build_tls_verify"""

    async with AsyncClient(timeout=TRANSMIT_TIMEOUT_SECONDS, verify=verify) as client:
        logger.debug(
            "Attempting to send notification %s of size %d to %s (attempt %d)",
            notification_id,
            len(content),
            remote_uri,
            attempt,
        )

        headers = {
            HEADER_SUBSCRIPTION_ID: subscription_href,
            HEADER_NOTIFICATION_ID: notification_id,
            HEADER_CONTENT_TYPE: SEP_XML_MIME,
        }

        transmit_start = utc_now()
        try:
            response = await client.post(url=remote_uri, content=content, headers=headers)

        except Exception as ex:
            logger.error(
                f"Exception {ex} sending notification {notification_id} of size {len(content)} to {remote_uri} (attempt {attempt})",  # noqa e501
                exc_info=ex,
            )
            # This is retryable - fire a NotificationTransmitError
            raise NotificationTransmitError(
                f"Exception {ex} sending notification {notification_id}",
                transmit_start=transmit_start,
                transmit_end=utc_now(),
                http_status_code=None,
            ) from ex

        transmit_end = utc_now()

        # Future work: Log these events in an audit log
        if response.status_code >= 200 and response.status_code < 299:
            # Success
            return TransmitResult(
                success=True,
                transmit_start=transmit_start,
                transmit_end=transmit_end,
                http_status_code=response.status_code,
            )

        if response.status_code >= 300 and response.status_code < 499:
            # On a 3XX or 4XX error - don't retry - we're either being redirected OR rejected for whatever reason
            logger.error(
                "Received HTTP %d sending notification %s of size %d to %s (attempt %d). No future retries",
                response.status_code,
                notification_id,
                len(content),
                remote_uri,
                attempt,
            )
            return TransmitResult(
                success=False,
                transmit_start=transmit_start,
                transmit_end=transmit_end,
                http_status_code=response.status_code,
            )

        # At this point it's likely an intermittent error - raise an exception that can potentially enable a retry
        msg = f"HTTP {response.status_code} sending notification {notification_id} of size {len(content)} to {remote_uri} (attempt {attempt})"  # noqa e501
        logger.error(msg)
        raise NotificationTransmitError(
            msg,
            transmit_start=transmit_start,
            transmit_end=utc_now(),
            http_status_code=response.status_code,
        )


async def claim_due_transmissions(session: AsyncSession, batch_size: int) -> list[ClaimedTransmit]:
    """Claims up to batch_size due notification_transmit rows (execute_after <= now). Each claimed row has its
    execute_after leased forward (see LEASE_SECONDS) within this transaction so other workers skip it while it's being
    sent. Returns detached snapshots of the claimed rows. The caller must commit the session to release the row locks
    before sending."""
    now = utc_now()
    # The FOR UPDATE SKIP LOCKED claim only stays multi-worker friendly while the planner can satisfy this ORDER BY by
    # using the index (ix_notification_transmit_execute_after). If any change forces a sort instead - eg ordering by a
    # non-indexed column, or in the wrong direction (ASC vs DESC), Postgres must read, lock and SKIP LOCKED-evaluate
    # EVERY matching row before it can sort+limit, so every worker locks every row.
    # Keep the ORDER BY aligned with an index (column + direction) if you touch this query!
    result = await session.execute(
        select(NotificationTransmit)
        .where(NotificationTransmit.execute_after <= now)
        .order_by(NotificationTransmit.execute_after)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = result.scalars().all()

    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    claimed: list[ClaimedTransmit] = []
    for r in rows:
        claimed.append(
            ClaimedTransmit(
                notification_transmit_id=r.notification_transmit_id,
                subscription_id=r.subscription_id,
                subscription_href=r.subscription_href,
                notification_id=r.notification_id,
                remote_uri=r.remote_uri,
                content=r.content,
                attempt=r.attempt,
            )
        )
        r.execute_after = lease_until
    return claimed


async def drop_to_dead_letter(session: AsyncSession, c: ClaimedTransmit, http_status_code: int | None) -> None:
    """Records an undelivered notification (that won't be retried) in the dead-letter table - preserving its content
    for debugging/replay - and removes it from the active queue."""
    session.add(
        NotificationDeadLetter(
            subscription_id=c.subscription_id,
            subscription_href=c.subscription_href,
            notification_id=c.notification_id,
            remote_uri=c.remote_uri,
            content=c.content,
            attempt=c.attempt,
            http_status_code=http_status_code,
        )
    )
    await session.execute(
        delete(NotificationTransmit).where(NotificationTransmit.notification_transmit_id == c.notification_transmit_id)
    )


async def process_transmit_batch(
    session_maker: async_sessionmaker[AsyncSession], verify: ssl.SSLContext | bool, batch_size: int
) -> int:
    """Claims and sends a batch of due notification_transmit rows. Row locks are released (and a lease applied) before
    any sending occurs so HTTP I/O never holds a row lock. On success the row is deleted; a retryable failure
    reschedules it via execute_after until retries are exhausted. Anything dropped without delivery (exhausted retries,
    a terminal 3xx/4xx, or an unexpected error) is moved to the dead-letter table. Every attempt is recorded in the
    TransmitNotificationLog. Returns the number of rows claimed."""

    async with session_maker() as session:
        async with session.begin():
            claimed = await claim_due_transmissions(session, batch_size)

    if not claimed:
        return 0

    # Send everything that was claimed (no row locks are held during this) and collect the outcomes
    outcomes = await asyncio.gather(
        *(
            do_transmit_notification(
                c.remote_uri, c.content, c.subscription_href, c.notification_id, c.attempt, verify=verify
            )
            for c in claimed
        ),
        return_exceptions=True,
    )

    async with session_maker() as session:
        async with session.begin():
            for c, outcome in zip(claimed, outcomes, strict=True):
                if isinstance(outcome, NotificationTransmitError):
                    session.add(create_transmit_notification_log(outcome, c.attempt, c.subscription_id, c.content))
                    delay = attempt_to_retry_delay(c.attempt)
                    if delay is None:
                        logger.error(
                            "Dead-lettering notification %s to %s - too many failed attempts",
                            c.notification_id,
                            c.remote_uri,
                        )
                        await drop_to_dead_letter(session, c, outcome.http_status_code)
                    else:
                        await session.execute(
                            update(NotificationTransmit)
                            .where(NotificationTransmit.notification_transmit_id == c.notification_transmit_id)
                            .values(attempt=c.attempt + 1, execute_after=utc_now() + delay)
                        )
                elif isinstance(outcome, TransmitResult):
                    session.add(create_transmit_notification_log(outcome, c.attempt, c.subscription_id, c.content))
                    if outcome.success:
                        await session.execute(
                            delete(NotificationTransmit).where(
                                NotificationTransmit.notification_transmit_id == c.notification_transmit_id
                            )
                        )
                    else:
                        # Terminal 3xx/4xx - the endpoint rejected it and we won't retry
                        await drop_to_dead_letter(session, c, outcome.http_status_code)
                else:
                    # An unexpected exception - this should never happen (do_transmit_notification only raises
                    # NotificationTransmitError for retryable errors). Dead-letter it so it can't wedge the queue
                    logger.error(
                        "Unexpected exception sending notification %s to %s. This will be dead-lettered.",
                        c.notification_id,
                        c.remote_uri,
                        exc_info=outcome,
                    )
                    await drop_to_dead_letter(session, c, None)

    return len(claimed)
