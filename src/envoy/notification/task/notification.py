import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Generic, Sequence

from httpx import AsyncClient
from taskiq import async_shared_broker

from envoy.notification.crud.batch import TResourceModel
from envoy.server.model.subscription import Subscription

HEADER_SUBSCRIPTION_ID = "x-envoy-subscription-href"

logger = logging.getLogger(__name__)


@dataclass
class Notification(Generic[TResourceModel]):
    """A notification represents a set of entities to communicate to remote URI via a subscription"""

    entities: Sequence[TResourceModel]  # The entities to send
    subscription: Subscription  # The subscription being serviced


async def schedule_retry_transmission(remote_uri: str, content: str, subscription_href: str, attempt: int) -> None:
    try:
        raise NotImplementedError()
    except Exception as ex:
        logger.error(
            "Exception retrying notification of size %d to %s (attempt %d)",
            len(content),
            remote_uri,
            attempt,
            exc_info=ex,
        )


async def _do_transmit_notification(remote_uri: str, content: str, subscription_href: str, attempt: int) -> None:
    """Internal method for transmitting the notification - doesn't handle exceptions"""

    # Big scary gotcha - There is no way (within the app layer) for a recipient of a notification
    # to validate that it's coming from our utility server. The ONLY thing keeping us safe
    # is the fact that CSIP recommends the use of mutual TLS which basically requires us to share our server
    # cert with the listener. This is all handled out of band and will be noted in the client docs
    # but I've put this message here for devs who read this code and get terrified. Good job on your keen security eye!
    async with AsyncClient(headers={HEADER_SUBSCRIPTION_ID: subscription_href}) as client:
        logger.debug("Attempting to send notification of size %d to %s (attempt %d)", len(content), remote_uri, attempt)
        response = await client.post(
            url=remote_uri,
            content=content,
        )

        if response.status_code >= 200 and response.status_code < 299:
            # Success
            return

        if response.status_code >= 300 and response.status_code < 499:
            # On a 3XX or 4XX error - don't retry
            logger.error(
                "Received HTTP %d sending notification of size %d to %s (attempt %d). No future retries",
                response.status_code,
                len(content),
                remote_uri,
                attempt,
            )
            return

        raise NotImplementedError()


@async_shared_broker.task()
async def handle_transmit_notification(remote_uri: str, content: str, subscription_href: str, attempt: int) -> None:
    """Call this to trigger an outgoing notification to be sent. If the notification fails it will be retried
    a few times (at a staggered cadence) before giving up.

    remote_uri: The FQDN / path where a HTTP POST will be issued
    content: The string that will form the body
    subscription_href: The href ID of the subscription that triggered this notification (eg /edev/3/sub/2)
    attempt: The attempt number - if this gets too high the notification will be dropped"""

    try:
        await _do_transmit_notification(remote_uri, content, subscription_href, attempt)
    except Exception as ex:
        logger.error(
            "Exception sending notification of size %d to %s (attempt %d)",
            len(content),
            remote_uri,
            attempt,
            exc_info=ex,
        )
        await schedule_retry_transmission(remote_uri, content, subscription_href, attempt)
