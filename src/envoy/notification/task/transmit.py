import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Optional, Union

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import AsyncBroker, TaskiqDepends, async_shared_broker

from envoy.notification.exception import NotificationTransmitError
from envoy.notification.handler import broker_dependency, session_dependency
from envoy.server.api.response import SEP_XML_MIME
from envoy.server.manager.time import utc_now
from envoy.server.model.subscription import TransmitNotificationLog

HEADER_SUBSCRIPTION_ID = "x-envoy-subscription-href"
HEADER_NOTIFICATION_ID = "x-envoy-notification-id"
HEADER_CONTENT_TYPE = "Content-Type"

logger = logging.getLogger(__name__)

TRANSMIT_TIMEOUT_SECONDS = 30
RETRY_DELAYS = [timedelta(seconds=10), timedelta(seconds=100), timedelta(seconds=300), timedelta(minutes=30)]


@dataclass(frozen=True, slots=False)
class TransmitResult:
    """Represents a success/error result in transmitting to a remote URI"""

    success: bool
    transmit_start: datetime  # tz aware start of transmission
    transmit_end: datetime  # tz aware end of transmission
    http_status_code: Optional[int]  # Can be None if there was a failure connecting / timeout


def create_transmit_notification_log(
    result: Union[TransmitResult, NotificationTransmitError], attempt: int, subscription_id: int, content: str
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


async def safely_log_transmit_result(
    session: AsyncSession,
    result: Union[TransmitResult, NotificationTransmitError],
    attempt: int,
    subscription_id: int,
    content: str,
) -> bool:
    """Attempts to log result into the TransmitNotificationLog via session. Guarantees that no exceptions will be raised

    Will commit the session"""
    try:
        log = create_transmit_notification_log(
            result=result, attempt=attempt, subscription_id=subscription_id, content=content
        )
        session.add(log)
        await session.commit()
        return True
    except Exception as exc:
        try:
            logger.error(f"safely_log_transmit_result: Unable to persist result {result}", exc_info=exc)
        except Exception:
            return False
        return False


def attempt_to_retry_delay(attempt: int) -> Optional[timedelta]:
    """Given the number of attempt just tried - return a delay that should be applied before attempting again (or none
    if no more attempts should be made)"""
    if attempt >= len(RETRY_DELAYS):
        return None

    return RETRY_DELAYS[attempt]


async def schedule_retry_transmission(
    broker: AsyncBroker,
    remote_uri: str,
    content: str,
    subscription_href: str,
    subscription_id: int,
    notification_id: str,
    attempt: int,
) -> None:
    delay = attempt_to_retry_delay(attempt)
    if delay is None:
        logger.error(f"Dropping {notification_id} to {remote_uri} - too many failed attempts")
        return

    try:
        await transmit_notification.kicker().with_broker(broker).with_labels(delay=int(delay.seconds)).kiq(
            remote_uri=remote_uri,
            content=content,
            subscription_href=subscription_href,
            subscription_id=subscription_id,
            notification_id=notification_id,
            attempt=attempt + 1,
        )
    except Exception as ex:
        logger.error(
            "Exception retrying notification of size %d to %s (attempt %d)",
            len(content),
            remote_uri,
            attempt,
            exc_info=ex,
        )


async def do_transmit_notification(
    remote_uri: str, content: str, subscription_href: str, notification_id: str, attempt: int
) -> TransmitResult:
    """Internal method for transmitting the notification - Raises a NotificationTransmitError if the request fails and
    needs retrying otherwise returns TransmitResult indicating the final result"""

    # Big scary gotcha - There is no way (within the app layer) for a recipient of a notification
    # to validate that it's coming from our utility server. The ONLY thing keeping us safe
    # is the fact that CSIP recommends the use of mutual TLS which basically requires us to share our server
    # cert with the listener. This is all handled out of band and will be noted in the client docs
    # but I've put this message here for devs who read this code and get terrified. Good job on your keen security eye!
    async with AsyncClient(timeout=TRANSMIT_TIMEOUT_SECONDS) as client:
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
            )

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


@async_shared_broker.task()
async def transmit_notification(
    remote_uri: str,
    content: str,
    subscription_href: str,
    subscription_id: int,
    notification_id: str,
    attempt: int,
    broker: Annotated[AsyncBroker, TaskiqDepends(broker_dependency)] = TaskiqDepends(),
    session: Annotated[AsyncSession, TaskiqDepends(session_dependency)] = TaskiqDepends(),
) -> None:
    """Call this to trigger an outgoing notification to be sent. If the notification fails it will be retried
    a few times (at a staggered cadence) before giving up.

    remote_uri: The FQDN / path where a HTTP POST will be issued
    content: The string that will form the body
    subscription_href: The href ID of the subscription that triggered this notification (eg /edev/3/sub/2)
    subscription_id: The ID of the subscription that triggered this notification
    attempt: The attempt number - if this gets too high the notification will be dropped"""

    try:
        transmit_result = await do_transmit_notification(
            remote_uri, content, subscription_href, notification_id, attempt
        )
        await safely_log_transmit_result(
            session=session, result=transmit_result, attempt=attempt, subscription_id=subscription_id, content=content
        )
    except NotificationTransmitError as notification_transmit_error:
        # This is the expected exception handler
        logger.error(
            "Exception sending notification of size %d to %s (attempt %d)",
            len(content),
            remote_uri,
            attempt,
            exc_info=notification_transmit_error,
        )
        await schedule_retry_transmission(
            broker, remote_uri, content, subscription_href, subscription_id, notification_id, attempt
        )
        await safely_log_transmit_result(
            session=session,
            result=notification_transmit_error,
            attempt=attempt,
            subscription_id=subscription_id,
            content=content,
        )
    except Exception as exc:
        # In theory this should never occur - it's only here if we get a "weird" exception
        logger.error(
            "Unexpected exception sending notification of size %d to %s (attempt %d). This will be dropped.",
            len(content),
            remote_uri,
            attempt,
            exc_info=exc,
        )
