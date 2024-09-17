import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from typing import Annotated, Generator, Generic, Iterable, Optional, Sequence, TypeVar, cast
from uuid import UUID, uuid4

from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier
from envoy_schema.server.schema.sep2.pub_sub import Notification as Sep2Notification
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import AsyncBroker, TaskiqDepends, async_shared_broker

from envoy.notification.crud.batch import (
    AggregatorBatchedEntities,
    TResourceModel,
    fetch_der_availability_by_changed_at,
    fetch_der_rating_by_changed_at,
    fetch_der_setting_by_changed_at,
    fetch_der_status_by_changed_at,
    fetch_does_by_changed_at,
    fetch_rates_by_changed_at,
    fetch_readings_by_changed_at,
    fetch_sites_by_changed_at,
    get_site_id,
    get_subscription_filter_id,
    select_subscriptions_for_resource,
)
from envoy.notification.exception import NotificationError
from envoy.notification.handler import broker_dependency, href_prefix_dependency, session_dependency
from envoy.notification.task.transmit import transmit_notification
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.mapper.sep2.pub_sub import NotificationMapper, SubscriptionMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_state import RequestStateParameters

logger = logging.getLogger(__name__)

MAX_NOTIFICATION_PAGE_SIZE = 100

DER_RESOURCES = set(
    [
        SubscriptionResource.SITE_DER_AVAILABILITY,
        SubscriptionResource.SITE_DER_RATING,
        SubscriptionResource.SITE_DER_SETTING,
        SubscriptionResource.SITE_DER_STATUS,
    ]
)


@dataclass
class NotificationEntities(Generic[TResourceModel]):
    """A notification represents a set of entities to communicate to remote URI via a subscription"""

    entities: Sequence[TResourceModel]  # The entities to send
    subscription: Subscription  # The subscription being serviced
    notification_id: UUID  # Unique ID for this notification (to detect retries)
    batch_key: tuple  # The batch key representing this particular batch of entities (see get_batch_key())
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
    resource: SubscriptionResource,
    sub: Subscription,
    batch_key: tuple,
    page_size: int,
    entities: Iterable[TResourceModel],
) -> Generator[NotificationEntities, None, None]:
    """Breaks a set of entities into pages that are represented by NotificationEntities."""
    if resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        # Tariff rates are special because each rate maps to 4 entities (one for each of the various prices)
        # So we need to handle this mapping here as we split everything into NotificationEntities
        entity_list = list(entities)  # We will be looping this multiple times so we need to stream it out
        for price_type in [
            PricingReadingType.IMPORT_ACTIVE_POWER_KWH,
            PricingReadingType.EXPORT_ACTIVE_POWER_KWH,
            PricingReadingType.IMPORT_REACTIVE_POWER_KVARH,
            PricingReadingType.EXPORT_REACTIVE_POWER_KVARH,
        ]:
            for entity_page in batched(entity_list, page_size):
                yield NotificationEntities(
                    entities=entity_page,
                    subscription=sub,
                    notification_id=uuid4(),
                    batch_key=batch_key,
                    pricing_reading_type=price_type,
                )
    elif resource in DER_RESOURCES:
        # DER resources can't be notified as a list - so treat these all as individual notifications
        for entity in entities:
            yield NotificationEntities(
                entities=[entity],
                subscription=sub,
                notification_id=uuid4(),
                batch_key=batch_key,
                pricing_reading_type=None,
            )
    else:
        for entity_page in batched(entities, page_size):
            yield NotificationEntities(
                entities=entity_page,
                subscription=sub,
                notification_id=uuid4(),
                batch_key=batch_key,
                pricing_reading_type=None,
            )


def entities_serviced_by_subscription(
    sub: Subscription, resource: SubscriptionResource, entities: list[TResourceModel]
) -> Generator[TResourceModel, None, None]:
    """Given a subscription - return the subset of entities that the subscription applies to."""
    if sub.resource_type != resource:
        return

    for e in entities:
        if sub.resource_id is not None and get_subscription_filter_id(resource, e) != sub.resource_id:
            continue

        if sub.scoped_site_id is not None and get_site_id(resource, e) != sub.scoped_site_id:
            continue

        # Check conditions (which will vary depending on the type of resource)
        conditions_matched = True
        if resource == SubscriptionResource.READING:
            for c in sub.conditions:
                if not conditions_matched:
                    break

                if c.attribute == ConditionAttributeIdentifier.READING_VALUE:
                    # If the reading is within the condition thresholds - don't include it
                    # (we only want values out of range)
                    reading_value = cast(SiteReading, e).value
                    low_range = c.lower_threshold is None or reading_value < c.lower_threshold
                    high_range = c.upper_threshold is None or reading_value > c.upper_threshold

                    if c.lower_threshold is not None and c.upper_threshold is not None:
                        conditions_matched = low_range or high_range
                    else:
                        conditions_matched = low_range and high_range

        if not conditions_matched:
            continue

        yield e


def entities_to_notification(
    resource: SubscriptionResource,
    sub: Subscription,
    batch_key: tuple,
    href_prefix: Optional[str],
    entities: Sequence[TResourceModel],
    pricing_reading_type: Optional[PricingReadingType],
) -> Sep2Notification:
    """Givens a subscription and associated entities - generate the notification content that will be sent out"""
    rs_params = RequestStateParameters(aggregator_id=sub.aggregator_id, aggregator_lfdi="", href_prefix=href_prefix)
    if resource == SubscriptionResource.SITE:
        return NotificationMapper.map_sites_to_response(cast(Sequence[Site], entities), sub, rs_params)
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        if pricing_reading_type is None:
            raise NotificationError("SubscriptionResource.TARIFF_GENERATED_RATE requires pricing_reading_type")

        # TARIFF_GENERATED_RATE: (aggregator_id: int, tariff_id: int, site_id: int, day: date)
        (_, tariff_id, site_id, day) = batch_key
        return NotificationMapper.map_rates_to_response(
            site_id=site_id,
            tariff_id=tariff_id,
            day=day,
            pricing_reading_type=pricing_reading_type,
            rates=cast(Sequence[TariffGeneratedRate], entities),
            sub=sub,
            rs_params=rs_params,
        )
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        # DYNAMIC_OPERATING_ENVELOPE: (aggregator_id: int, site_id: int)
        (_, site_id) = batch_key
        return NotificationMapper.map_does_to_response(
            site_id, cast(Sequence[DynamicOperatingEnvelope], entities), sub, rs_params
        )
    elif resource == SubscriptionResource.READING:
        # READING: (aggregator_id: int, site_id: int, site_reading_type_id: int)
        (_, site_id, site_reading_type_id) = batch_key
        return NotificationMapper.map_readings_to_response(
            site_id, site_reading_type_id, cast(Sequence[SiteReading], entities), sub, rs_params
        )
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        # SITE_DER_AVAILABILITY: (aggregator_id: int, site_id: int, site_der_id: int)
        (_, site_id, site_der_id) = batch_key
        availability = cast(SiteDERAvailability, entities[0]) if len(entities) > 0 else None
        return NotificationMapper.map_der_availability_to_response(
            site_id, site_der_id, availability, sub, rs_params
        )  # We will only EVER have single element lists for this resource
    elif resource == SubscriptionResource.SITE_DER_RATING:
        # SITE_DER_RATING: (aggregator_id: int, site_id: int, site_der_id: int)
        (_, site_id, site_der_id) = batch_key
        rating = cast(SiteDERRating, entities[0]) if len(entities) > 0 else None
        return NotificationMapper.map_der_rating_to_response(
            site_id, site_der_id, rating, sub, rs_params
        )  # We will only EVER have single element lists for this resource
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        # SITE_DER_SETTING: (aggregator_id: int, site_id: int, site_der_id: int)
        (_, site_id, site_der_id) = batch_key
        settings = cast(SiteDERSetting, entities[0]) if len(entities) > 0 else None
        return NotificationMapper.map_der_settings_to_response(
            site_id, site_der_id, settings, sub, rs_params
        )  # We will only EVER have single element lists for this resource
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        # SITE_DER_STATUS: (aggregator_id: int, site_id: int, site_der_id: int)
        (_, site_id, site_der_id) = batch_key
        status = cast(SiteDERStatus, entities[0]) if len(entities) > 0 else None
        return NotificationMapper.map_der_status_to_response(
            site_id, site_der_id, status, sub, rs_params
        )  # We will only EVER have single element lists for this resource
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify way to map entities")


async def fetch_batched_entities(
    session: AsyncSession, resource: SubscriptionResource, timestamp: datetime
) -> AggregatorBatchedEntities:
    """Fetches the set of AggregatorBatchedEntities for the specified resource at the specified timestamp"""
    if resource == SubscriptionResource.SITE:
        return await fetch_sites_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.READING:
        return await fetch_readings_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        return await fetch_does_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        return await fetch_rates_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        return await fetch_der_availability_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.SITE_DER_RATING:
        return await fetch_der_rating_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        return await fetch_der_setting_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        return await fetch_der_status_by_changed_at(session, timestamp)
    else:
        raise NotificationError(f"Unsupported resource type: {resource}")


@async_shared_broker.task()
async def check_db_upsert(
    resource: SubscriptionResource,
    timestamp_epoch: float,
    href_prefix: Annotated[Optional[str], TaskiqDepends(href_prefix_dependency)] = TaskiqDepends(),
    session: Annotated[AsyncSession, TaskiqDepends(session_dependency)] = TaskiqDepends(),
    broker: Annotated[AsyncBroker, TaskiqDepends(broker_dependency)] = TaskiqDepends(),
) -> None:
    """Call this to notify that a particular timestamp within a particular named resource
    has had a batch of inserts/updates such that requesting all records with that changed_at timestamp
    will yield all resources to be inspected for potentially notifying subscribers

    resource_name: The name of the resource that is being checked for changes
    timestamp: The datetime.timestamp() that will be used for finding resources (must be exact match)"""

    timestamp = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)
    logger.debug("check_db_upsert for resource %s at timestamp %s", resource, timestamp)

    batched_entities = await fetch_batched_entities(session, resource, timestamp)

    # Now generate subscription notifications
    all_notifications: list[NotificationEntities] = []
    aggregator_subs_cache: dict[int, Sequence[Subscription]] = {}  # keyed by aggregator_id
    for batch_key, entities in batched_entities.models_by_batch_key.items():
        agg_id: int = batch_key[0]  # The aggregator_id is ALWAYS first in the batch key by definition

        # We enumerate by aggregator ID at the top level (as a way of minimising the size of entities)
        # We also cache the per aggregator subscriptions to minimise round trips to the db
        candidate_subscriptions = aggregator_subs_cache.get(agg_id, None)
        if candidate_subscriptions is None:
            candidate_subscriptions = await select_subscriptions_for_resource(session, agg_id, resource)
            aggregator_subs_cache[agg_id] = candidate_subscriptions

        for sub in candidate_subscriptions:
            # Break the entities that apply to this subscription down into "pages" according to
            # the definition of the subscription
            entity_limit = sub.entity_limit if sub.entity_limit > 0 else 1
            if entity_limit > MAX_NOTIFICATION_PAGE_SIZE:
                entity_limit = MAX_NOTIFICATION_PAGE_SIZE

            entities_to_notify = entities_serviced_by_subscription(sub, resource, entities)
            all_notifications.extend(get_entity_pages(resource, sub, batch_key, entity_limit, entities_to_notify))

    # Finally time to enqueue the outgoing notifications
    logger.info(
        "check_db_upsert for resource %s at timestamp %s generated %d notifications",
        resource,
        timestamp,
        len(all_notifications),
    )
    for n in all_notifications:
        content = entities_to_notification(
            resource, n.subscription, n.batch_key, href_prefix, n.entities, n.pricing_reading_type
        ).to_xml(skip_empty=False, exclude_none=True, exclude_unset=True)
        if isinstance(content, bytes):
            content = content.decode()

        agg_id = n.batch_key[0]  # Aggregator ID is ALWAYS the first element of the batch_key
        rs_params = RequestStateParameters(aggregator_id=agg_id, aggregator_lfdi="", href_prefix=href_prefix)

        try:
            await transmit_notification.kicker().with_broker(broker).kiq(
                remote_uri=n.subscription.notification_uri,
                content=content,
                notification_id=str(n.notification_id),
                subscription_href=SubscriptionMapper.calculate_subscription_href(n.subscription, rs_params),
                attempt=0,
            )
        except Exception as ex:
            logger.error("Error adding transmission task", exc_info=ex)
