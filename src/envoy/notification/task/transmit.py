import logging
from datetime import timedelta
from typing import Annotated, Optional

from httpx import AsyncClient
from taskiq import AsyncBroker, TaskiqDepends, async_shared_broker

from envoy.notification.exception import NotificationError
from envoy.notification.handler import broker_dependency

HEADER_SUBSCRIPTION_ID = "x-envoy-subscription-href"
HEADER_NOTIFICATION_ID = "x-envoy-notification-id"

logger = logging.getLogger(__name__)


RETRY_DELAYS = [timedelta(seconds=10), timedelta(seconds=100), timedelta(seconds=300), timedelta(minutes=30)]


def attempt_to_retry_delay(attempt: int) -> Optional[timedelta]:
    """Given the number of attempt just tried - return a delay that should be applied before attempting again (or none
    if no more attempts should be made)"""
    if attempt >= len(RETRY_DELAYS):
        return None

    return RETRY_DELAYS[attempt]


async def schedule_retry_transmission(
    broker: AsyncBroker, remote_uri: str, content: str, subscription_href: str, notification_id: str, attempt: int
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
) -> bool:
    """Internal method for transmitting the notification - Raises a NotificationError if the request fails and
    needs retrying otherwise returns true if the transmit succeeded or false otherwise"""

    # Big scary gotcha - There is no way (within the app layer) for a recipient of a notification
    # to validate that it's coming from our utility server. The ONLY thing keeping us safe
    # is the fact that CSIP recommends the use of mutual TLS which basically requires us to share our server
    # cert with the listener. This is all handled out of band and will be noted in the client docs
    # but I've put this message here for devs who read this code and get terrified. Good job on your keen security eye!
    async with AsyncClient() as client:
        logger.debug(
            "Attempting to send notification %s of size %d to %s (attempt %d)",
            notification_id,
            len(content),
            remote_uri,
            attempt,
        )

        headers = {HEADER_SUBSCRIPTION_ID: subscription_href, HEADER_NOTIFICATION_ID: notification_id}

        try:
            response = await client.post(url=remote_uri, content=content, headers=headers)
        except Exception as ex:
            logger.error(
                f"Exception {ex} sending notification {notification_id} of size {len(content)} to {remote_uri} (attempt {attempt})",  # noqa e501
                exc_info=ex,
            )
            raise NotificationError(f"Exception {ex} sending notification {notification_id}")

        # Future work: Log these events in an audit log
        if response.status_code >= 200 and response.status_code < 299:
            # Success
            return True

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
            return False

        # At this point it's likely an intermittent error - raise an exception that can potentially enable a retry
        msg = f"HTTP {response.status_code} sending notification {notification_id} of size {len(content)} to {remote_uri} (attempt {attempt})"  # noqa e501
        logger.error(msg)
        raise NotificationError(msg)


@async_shared_broker.task()
async def transmit_notification(
    remote_uri: str,
    content: str,
    subscription_href: str,
    notification_id: str,
    attempt: int,
    broker: Annotated[AsyncBroker, TaskiqDepends(broker_dependency)] = TaskiqDepends(),
) -> None:
    """Call this to trigger an outgoing notification to be sent. If the notification fails it will be retried
    a few times (at a staggered cadence) before giving up.

    remote_uri: The FQDN / path where a HTTP POST will be issued
    content: The string that will form the body
    subscription_href: The href ID of the subscription that triggered this notification (eg /edev/3/sub/2)
    attempt: The attempt number - if this gets too high the notification will be dropped"""

    try:
        await do_transmit_notification(remote_uri, content, subscription_href, notification_id, attempt)
    except Exception as ex:
        logger.error(
            "Exception sending notification of size %d to %s (attempt %d)",
            len(content),
            remote_uri,
            attempt,
            exc_info=ex,
        )
        await schedule_retry_transmission(broker, remote_uri, content, subscription_href, notification_id, attempt)
