from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from typing import Annotated, Generator, Generic, Iterable, Literal, Optional, Sequence, TypeVar, Union, cast
from uuid import UUID, uuid4

from envoy_schema.server.schema.sep2.pub_sub import Notification as Sep2Notification
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import AsyncBroker, Context, TaskiqDepends, async_shared_broker

from envoy.notification.crud.batch import (
    AggregatorBatchedEntities,
    TResourceModel,
    fetch_does_by_changed_at,
    fetch_rates_by_changed_at,
    fetch_readings_by_changed_at,
    fetch_sites_by_changed_at,
    get_primary_key,
    get_site_id,
    select_subscriptions_for_resource,
)
from envoy.notification.main import broker_dependency, href_prefix_dependency, session_dependency
from envoy.notification.task.transmit import transmit_notification
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.mapper.sep2.pub_sub import NotificationMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate

MAX_NOTIFICATION_PAGE_SIZE = 100


@dataclass
class NotificationEntities(Generic[TResourceModel]):
    """A notification represents a set of entities to communicate to remote URI via a subscription"""

    entities: Sequence[TResourceModel]  # The entities to send
    subscription: Subscription  # The subscription being serviced
    notification_id: UUID  # Unique ID for this notification (to detect retries)
    site_id: int  # The
    pricing_reading_type: Optional[PricingReadingType]


T = TypeVar("T")


def batched(iterable: Iterable[T], chunk_size: int) -> Generator[list[T], None, None]:
    """This is a equivalent attempt at implementing the python 3.12 itertools.batched function.

    It splits a sequence of values into chunks of a fixed size, yielding chunks until nothing is left.

    Eg: batched([1,2,3,4,5], 2) will yield the following chunks in an iterator: [1,2] then [3,4] then [5] before
    finishing"""

    iterator = iter(iterable)
    while chunk := list(islice(iterator, chunk_size)):
        yield chunk


def get_entity_pages(
    resource: SubscriptionResource, sub: Subscription, site_id: int, page_size: int, entities: Iterable[TResourceModel]
) -> Generator[NotificationEntities, None, None]:
    """Breaks a set of entities into pages that are represented by NotificationEntities."""
    if resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        # Tariff rates are special because each rate maps to 4 entities (one for each of the various prices)
        # So we need to handle this mapping here as we split everything into NotificationEntities
        for price_type in [
            PricingReadingType.IMPORT_ACTIVE_POWER_KWH,
            PricingReadingType.EXPORT_ACTIVE_POWER_KWH,
            PricingReadingType.IMPORT_REACTIVE_POWER_KVARH,
            PricingReadingType.EXPORT_REACTIVE_POWER_KVARH,
        ]:
            for entity_page in batched(entities, page_size):
                yield NotificationEntities(
                    entities=entity_page,
                    subscription=sub,
                    notification_id=uuid4(),
                    site_id=site_id,
                    pricing_reading_type=price_type,
                )
    else:
        for entity_page in batched(entities, page_size):
            yield NotificationEntities(
                entities=entity_page,
                subscription=sub,
                notification_id=uuid4(),
                site_id=site_id,
                pricing_reading_type=None,
            )


def entities_serviced_by_subscription(
    sub: Subscription, resource: SubscriptionResource, entities: list[TResourceModel]
) -> list[TResourceModel]:
    """Given a subscription - return the subset of entities that the subscription applies to."""
    if sub.resource_type != resource:
        return []

    return [
        e
        for e in entities
        if (sub.resource_id is None or get_primary_key(resource, e) == sub.resource_id)
        and (sub.scoped_site_id is None or get_site_id(resource, e) == sub.scoped_site_id)
    ]


def entities_to_notification(
    resource: SubscriptionResource,
    sub: Subscription,
    site_id: int,
    href_prefix: Optional[str],
    entities: Sequence[TResourceModel],
    pricing_reading_type: Optional[PricingReadingType],
) -> Sep2Notification:
    """Givens a subscription and associated entities - generate the notification content that will be sent out"""
    if resource == SubscriptionResource.SITE:
        return NotificationMapper.map_sites_to_response(cast(Sequence[Site], entities), sub, href_prefix)
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        return NotificationMapper.map_rates_to_response(
            pricing_reading_type, cast(Sequence[TariffGeneratedRate], entities), sub, href_prefix
        )
    else:
        raise Exception(f"{resource} is unsupported - unable to identify way to map entities")


@async_shared_broker.task()
async def check_db_upsert(
    session: Annotated[AsyncSession, TaskiqDepends(session_dependency)],
    broker: Annotated[AsyncBroker, TaskiqDepends(broker_dependency)],
    href_prefix: Annotated[Optional[str], TaskiqDepends(href_prefix_dependency)],
    resource: SubscriptionResource,
    timestamp_epoch: float,
) -> None:
    """Call this to notify that a particular timestamp within a particular named resource
    has had a batch of inserts/updates such that requesting all records with that changed_at timestamp
    will yield all resources to be inspected for potentially notifying subscribers

    resource_name: The name of the resource that is being checked for changes
    timestamp: The datetime.timestamp() that will be used for finding resources (must be exact match)"""

    timestamp = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)

    batched_entities: AggregatorBatchedEntities
    if resource == SubscriptionResource.SITE:
        batched_entities = await fetch_sites_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.READING:
        batched_entities = await fetch_readings_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        batched_entities = await fetch_does_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        batched_entities = await fetch_rates_by_changed_at(session, timestamp)
    else:
        raise Exception(f"Unsupported resource type: {resource}")

    # Now generate subscription notifications
    all_notifications: list[NotificationEntities] = []
    for agg_id, site_mapped_entities in batched_entities.models_by_aggregator_then_site_id.items():
        for site_id, entities in site_mapped_entities.items():
            # We enumerate by aggregator ID at the top level (as a way of minimising the size of entities)
            candidate_subscriptions = await select_subscriptions_for_resource(session, agg_id, resource)
            for sub in candidate_subscriptions:
                # Break the entities that apply to this subscription down into "pages" according to
                # the definition of the subscription
                entity_limit = sub.entity_limit if sub.entity_limit > 0 else 1
                if entity_limit > MAX_NOTIFICATION_PAGE_SIZE:
                    entity_limit = MAX_NOTIFICATION_PAGE_SIZE

                entities_to_notify = entities_serviced_by_subscription(sub, resource, entities)
                all_notifications.extend(get_entity_pages(resource, sub, site_id, entity_limit, entities_to_notify))

    # Finally time to enqueue the outgoing notifications
    for n in all_notifications:
        content = entities_to_notification(resource, n.subscription, href_prefix, n.entities).to_xml(skip_empty=True)
        if isinstance(content, bytes):
            content = content.decode()

        await transmit_notification.kicker().with_broker(broker).kiq(
            remote_uri=n.subscription.notification_uri,
            content=content,
            notification_id=n.notification_id,
            subscription_href=NotificationMapper.calculate_subscription_href(n.subscription),
            attempt=0,
        )
