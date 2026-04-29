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
    fetch_default_site_controls_by_changed_at,
    fetch_der_availability_by_changed_at,
    fetch_der_rating_by_changed_at,
    fetch_der_setting_by_changed_at,
    fetch_der_status_by_changed_at,
    fetch_does_by_changed_at,
    fetch_fsa_by_changed_at,
    fetch_rates_by_changed_at,
    fetch_readings_by_changed_at,
    fetch_site_control_groups_by_changed_at,
    fetch_sites_by_changed_at,
    fetch_tariff_components_by_changed_at,
    fetch_tariffs_by_changed_at,
    get_site_id,
    get_subscription_filter_id,
    select_subscriptions_for_resource,
)
from envoy.notification.crud.common import (
    SiteScopedFunctionSetAssignment,
    SiteScopedSiteControlGroup,
    SiteScopedSiteControlGroupDefault,
    SiteScopedTariff,
    SiteScopedTariffComponent,
    TArchiveResourceModel,
    TResourceModel,
)
from envoy.notification.exception import NotificationError
from envoy.notification.handler import broker_dependency, href_prefix_dependency, session_dependency
from envoy.notification.task.transmit import transmit_notification
from envoy.server.crud.site import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.manager.server import RuntimeServerConfigManager, _map_server_config
from envoy.server.manager.time import utc_now
from envoy.server.mapper.sep2.pub_sub import NotificationMapper, NotificationType, SubscriptionMapper
from envoy.server.model.config.server import RuntimeServerConfig
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import AggregatorRequestScope, CertificateType

logger = logging.getLogger(__name__)

MAX_NOTIFICATION_PAGE_SIZE = 100

NON_LIST_RESOURCES = set(
    [
        SubscriptionResource.SITE_DER_AVAILABILITY,
        SubscriptionResource.SITE_DER_RATING,
        SubscriptionResource.SITE_DER_SETTING,
        SubscriptionResource.SITE_DER_STATUS,
        SubscriptionResource.DEFAULT_SITE_CONTROL,
    ]
)


@dataclass
class NotificationEntities(Generic[TResourceModel]):
    """A notification represents a set of entities to communicate to remote URI via a subscription"""

    entities: Sequence[TResourceModel]  # The entities to send
    subscription: Subscription  # The subscription being serviced
    notification_id: UUID  # Unique ID for this notification (to detect retries)
    notification_type: NotificationType  # Is this notification for a change in or deletion of these entities
    batch_key: tuple  # The batch key representing this particular batch of entities (see get_batch_key())


T = TypeVar("T")


def scope_for_subscription(sub: Subscription, href_prefix: Optional[str]) -> AggregatorRequestScope:
    """Generates a request scope for use with a subscription when mapping elements"""
    return AggregatorRequestScope(
        aggregator_id=sub.aggregator_id,
        display_site_id=(VIRTUAL_END_DEVICE_SITE_ID if sub.scoped_site_id is None else sub.scoped_site_id),
        site_id=sub.scoped_site_id,
        sfdi=0,
        lfdi="",
        href_prefix=href_prefix,
        iana_pen=0,
        source=CertificateType.AGGREGATOR_CERTIFICATE,
    )


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
    notification_type: NotificationType,
) -> Generator[NotificationEntities, None, None]:
    """Breaks a set of entities into pages that are represented by NotificationEntities."""
    if resource in NON_LIST_RESOURCES:
        # DER resources can't be notified as a list - so treat these all as individual notifications
        for entity in entities:
            yield NotificationEntities(
                entities=[entity],
                subscription=sub,
                notification_id=uuid4(),
                notification_type=notification_type,
                batch_key=batch_key,
            )
    else:
        for entity_page in batched(entities, page_size):
            yield NotificationEntities(
                entities=entity_page,
                subscription=sub,
                notification_id=uuid4(),
                notification_type=notification_type,
                batch_key=batch_key,
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
                    reading_value = cast(SiteReading, e).value  # type: ignore # mypy quirk
                    low_range = c.lower_threshold is None or reading_value < c.lower_threshold
                    high_range = c.upper_threshold is None or reading_value > c.upper_threshold

                    if c.lower_threshold is not None and c.upper_threshold is not None:
                        conditions_matched = low_range or high_range
                    else:
                        conditions_matched = low_range and high_range

        if not conditions_matched:
            continue

        yield e


def all_entity_batches(
    changed_batches: dict[tuple, list[TResourceModel]],
    deleted_batches: dict[tuple, list[TArchiveResourceModel]],
) -> Generator[tuple[tuple, int, list[TResourceModel], NotificationType], None, None]:
    """Enumerates every batch of entities in batch. Each batch will be returned with the batch key and whether
    it's a delete or change batch

    returns a tuple in the form:
      (batch_key: tuple, aggregator_id: int, entities: list[TResourceModel], notification_type: NotificationType)

    NOTE: The returned entities will be duck typed into TResourceModel but can also include equivalent the duck typed
    equivalent TArchiveResourceModel (eg - ArchiveSite will be typed as Site)
    """
    for batch_key, changed_entities in changed_batches.items():
        agg_id: int = batch_key[0]  # The aggregator_id is ALWAYS first in the batch key by definition
        yield (batch_key, agg_id, changed_entities, NotificationType.ENTITY_CHANGED)

    for batch_key, deleted_entities in deleted_batches.items():
        agg_id = batch_key[0]  # The aggregator_id is ALWAYS first in the batch key by definition

        # This is duck typing the archive model to the "source" model. We have unit tests elsewhere that enforce
        # that these type definitions stay in sync
        yield (batch_key, agg_id, cast(list[TResourceModel], deleted_entities), NotificationType.ENTITY_DELETED)


def entities_to_notification(  # noqa: C901
    resource: SubscriptionResource,
    sub: Subscription,
    batch_key: tuple,
    href_prefix: Optional[str],
    notification_type: NotificationType,
    entities: Sequence[TResourceModel],
    config: RuntimeServerConfig,
) -> Sep2Notification:
    """Givens a subscription and associated entities - generate the notification content that will be sent out"""
    scope = scope_for_subscription(sub, href_prefix)
    if resource == SubscriptionResource.SITE:
        return NotificationMapper.map_sites_to_response(
            cast(Sequence[Site], entities), sub, scope, notification_type, config.disable_edev_registration, config.edevl_pollrate_seconds  # type: ignore # mypy quirk # noqa: E501
        )
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:

        # TARIFF_GENERATED_RATE: (aggregator_id: int, tariff_id: int, site_id: int, tariff_component_id: int)
        _, tariff_id, _, tariff_component_id = batch_key
        return NotificationMapper.map_rates_to_response(
            tariff_id=tariff_id,
            tariff_component_id=tariff_component_id,
            rates=cast(Sequence[TariffGeneratedRate], entities),  # type: ignore # mypy quirk
            sub=sub,
            scope=scope,
            notification_type=notification_type,
            now=utc_now(),
        )
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        # DYNAMIC_OPERATING_ENVELOPE: (aggregator_id: int, site_id: int, site_control_group_id: int)
        _, _, site_control_group_id = batch_key
        return NotificationMapper.map_does_to_response(
            site_control_group_id=site_control_group_id,
            does=cast(Sequence[DynamicOperatingEnvelope], entities),  # type: ignore
            sub=sub,
            scope=scope,
            notification_type=notification_type,
            power10_multiplier=config.site_control_pow10_encoding,
        )
    elif resource == SubscriptionResource.SITE_CONTROL_GROUP:
        # SITE_CONTROL_GROUP: (aggregator_id: int, site_control_group_id: int)
        return NotificationMapper.map_site_control_groups_to_response(
            site_control_groups=[e.original for e in cast(Sequence[SiteScopedSiteControlGroup], entities)],  # type: ignore # noqa: E501
            sub=sub,
            scope=scope,
            notification_type=notification_type,
            poll_rate_seconds=config.derpl_pollrate_seconds,
        )
    elif resource == SubscriptionResource.READING:
        # READING: (aggregator_id: int, site_id: int, site_reading_type_id: int)
        _, _, group_id = batch_key
        return NotificationMapper.map_readings_to_response(
            group_id, cast(Sequence[SiteReading], entities), sub, scope, notification_type  # type: ignore
        )
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        # SITE_DER_AVAILABILITY: (aggregator_id: int, site_id: int, site_der_id: int)
        _, site_id, site_der_id = batch_key
        availability = cast(SiteDERAvailability, entities[0]) if len(entities) > 0 else None  # type: ignore
        return NotificationMapper.map_der_availability_to_response(
            site_der_id, availability, site_id, sub, scope, notification_type
        )  # We will only EVER have single element lists for this resource
    elif resource == SubscriptionResource.SITE_DER_RATING:
        # SITE_DER_RATING: (aggregator_id: int, site_id: int, site_der_id: int)
        _, site_id, site_der_id = batch_key
        rating = cast(SiteDERRating, entities[0]) if len(entities) > 0 else None  # type: ignore # mypy quirk
        return NotificationMapper.map_der_rating_to_response(
            site_der_id, rating, site_id, sub, scope, notification_type
        )  # We will only EVER have single element lists for this resource
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        # SITE_DER_SETTING: (aggregator_id: int, site_id: int, site_der_id: int)
        _, site_id, site_der_id = batch_key
        settings = cast(SiteDERSetting, entities[0]) if len(entities) > 0 else None  # type: ignore # mypy quirk
        return NotificationMapper.map_der_settings_to_response(
            site_der_id, settings, site_id, sub, scope, notification_type
        )  # We will only EVER have single element lists for this resource
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        # SITE_DER_STATUS: (aggregator_id: int, site_id: int, site_der_id: int)
        _, site_id, site_der_id = batch_key
        status = cast(SiteDERStatus, entities[0]) if len(entities) > 0 else None  # type: ignore # mypy quirk
        return NotificationMapper.map_der_status_to_response(
            site_der_id, status, site_id, sub, scope, notification_type
        )  # We will only EVER have single element lists for this resource
    elif resource == SubscriptionResource.FUNCTION_SET_ASSIGNMENTS:
        # FUNCTION_SET_ASSIGNMENTS: (aggregator_id: int, site_id: int)
        _, site_id = batch_key
        site_scoped_server_config = cast(SiteScopedFunctionSetAssignment, entities[0]) if len(entities) > 0 else None
        poll_rate = site_scoped_server_config.function_set_assignment_poll_rate if site_scoped_server_config else None
        if poll_rate is None:
            poll_rate = _map_server_config(None).fsal_pollrate_seconds

        new_fsa_ids = site_scoped_server_config.function_set_assignment_ids if site_scoped_server_config else []

        return NotificationMapper.map_function_set_assignments_list_to_response(
            poll_rate, sub, scope, notification_type, new_fsa_ids
        )

    elif resource == SubscriptionResource.DEFAULT_SITE_CONTROL:
        # DEFAULT_SITE_CONTROL: (aggregator_id: int, site_id: int, site_control_group_id: int)
        _, site_id, site_control_group_id = batch_key
        default_site_control = cast(SiteScopedSiteControlGroupDefault, entities[0]) if len(entities) > 0 else None

        return NotificationMapper.map_default_site_control_response(
            None if default_site_control is None else default_site_control.original,
            site_control_group_id,
            config.site_control_pow10_encoding,
            sub,
            scope,
            notification_type,
        )
    elif resource == SubscriptionResource.TARIFF_COMPONENT:
        # TARIFF_COMPONENT: (aggregator_id: int, site_id: int, tariff_id: int)
        _, site_id, tariff_id = batch_key

        tariff_components = [cast(SiteScopedTariffComponent, e).original for e in entities]

        return NotificationMapper.map_rate_components_to_response(
            tariff_id, tariff_components, sub, scope, notification_type
        )
    elif resource == SubscriptionResource.TARIFF:
        # TARIFF: (aggregator_id: int, site_id: int)

        tariffs = [cast(SiteScopedTariff, e).original for e in entities]

        return NotificationMapper.map_tariffs_to_response(tariffs, sub, scope, notification_type)
    elif resource == SubscriptionResource.COMBINED_TARIFF_GENERATED_RATE:

        # COMBINED_TARIFF_GENERATED_RATE: (aggregator_id: int, tariff_id: int, site_id: int)
        _, tariff_id, _ = batch_key
        return NotificationMapper.map_rates_to_response(
            tariff_id=tariff_id,
            tariff_component_id=None,
            rates=cast(Sequence[TariffGeneratedRate], entities),  # type: ignore # mypy quirk
            sub=sub,
            scope=scope,
            notification_type=notification_type,
            now=utc_now(),
        )

    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify way to map entities")


async def fetch_batched_entities(
    session: AsyncSession, resource: SubscriptionResource, timestamp: datetime
) -> list[AggregatorBatchedEntities]:
    """Fetches the set of AggregatorBatchedEntities for the specified resource at the specified timestamp"""
    if resource == SubscriptionResource.SITE:
        return [await fetch_sites_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.READING:
        return [await fetch_readings_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        return [await fetch_does_by_changed_at(session, timestamp)]
    elif (
        resource == SubscriptionResource.TARIFF_GENERATED_RATE
        or resource == SubscriptionResource.COMBINED_TARIFF_GENERATED_RATE
    ):
        return await fetch_rates_by_changed_at(session, timestamp)
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        return [await fetch_der_availability_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.SITE_DER_RATING:
        return [await fetch_der_rating_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        return [await fetch_der_setting_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        return [await fetch_der_status_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.DEFAULT_SITE_CONTROL:
        return [await fetch_default_site_controls_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.FUNCTION_SET_ASSIGNMENTS:
        return [await fetch_fsa_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.SITE_CONTROL_GROUP:
        return [await fetch_site_control_groups_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.TARIFF:
        return [await fetch_tariffs_by_changed_at(session, timestamp)]
    elif resource == SubscriptionResource.TARIFF_COMPONENT:
        return [await fetch_tariff_components_by_changed_at(session, timestamp)]
    else:
        raise NotificationError(f"Unsupported resource type: {resource}")


async def handle_batch(
    session: AsyncSession, batch: AggregatorBatchedEntities, href_prefix: Optional[str], broker: AsyncBroker
) -> None:
    """Given a batch of entities for a subscription type - turn those entities into a series of notifications"""
    all_notifications: list[NotificationEntities] = []
    aggregator_subs_cache: dict[int, Sequence[Subscription]] = {}  # keyed by aggregator_id
    for batch_key, agg_id, entities, notification_type in all_entity_batches(
        batch.models_by_batch_key, batch.deleted_by_batch_key
    ):

        # We enumerate by aggregator ID at the top level (as a way of minimising the size of entities)
        # We also cache the per aggregator subscriptions to minimise round trips to the db
        candidate_subscriptions = aggregator_subs_cache.get(agg_id, None)
        if candidate_subscriptions is None:
            candidate_subscriptions = await select_subscriptions_for_resource(session, agg_id, batch.resource)
            aggregator_subs_cache[agg_id] = candidate_subscriptions

        for sub in candidate_subscriptions:
            # Break the entities that apply to this subscription down into "pages" according to
            # the definition of the subscription
            entity_limit = sub.entity_limit if sub.entity_limit > 0 else 1
            if entity_limit > MAX_NOTIFICATION_PAGE_SIZE:
                entity_limit = MAX_NOTIFICATION_PAGE_SIZE

            if entities:
                # Normally we're going to have a batch of entities that should be sent out via notifications
                entities_to_notify = entities_serviced_by_subscription(sub, batch.resource, entities)
                all_notifications.extend(
                    get_entity_pages(
                        batch.resource, sub, batch_key, entity_limit, entities_to_notify, notification_type
                    )
                )
            else:
                # But we can end up in this state if the subscription is at the List and an attribute on the list has
                # changed (eg pollRate) - i.e. there are no child list items to indicate as changed - JUST the list.
                if sub.resource_type == batch.resource:
                    # All we need is a match on the type of subscription to generate the subscription
                    all_notifications.append(
                        NotificationEntities(
                            entities=[],  # No entities - we're just wanting the parent List to notify as empty
                            subscription=sub,
                            notification_id=uuid4(),
                            notification_type=NotificationType.ENTITY_CHANGED,
                            batch_key=batch_key,
                        )
                    )

    # Finally time to enqueue the outgoing notifications
    logger.info(
        "check_db_change_or_delete for resource %s at timestamp %s generated %d notifications",
        batch.resource,
        batch.timestamp,
        len(all_notifications),
    )

    # fetch runtime server config
    config = await RuntimeServerConfigManager.fetch_current_config(session)

    for n in all_notifications:
        content = entities_to_notification(
            batch.resource,
            n.subscription,
            n.batch_key,
            href_prefix,
            n.notification_type,
            n.entities,
            config,
        ).to_xml(skip_empty=False, exclude_none=True, exclude_unset=True)
        if isinstance(content, bytes):
            content = content.decode()

        agg_id = n.batch_key[0]  # Aggregator ID is ALWAYS the first element of the batch_key
        scope = scope_for_subscription(n.subscription, href_prefix)

        try:
            await transmit_notification.kicker().with_broker(broker).kiq(
                remote_uri=n.subscription.notification_uri,
                content=content,
                notification_id=str(n.notification_id),
                subscription_href=SubscriptionMapper.calculate_subscription_href(n.subscription, scope),
                subscription_id=n.subscription.subscription_id,
                attempt=0,
            )
        except Exception as ex:
            logger.error("Error adding transmission task", exc_info=ex)


@async_shared_broker.task()
async def check_db_change_or_delete(
    resource: SubscriptionResource,
    timestamp_epoch: float,
    href_prefix: Annotated[Optional[str], TaskiqDepends(href_prefix_dependency)] = TaskiqDepends(),
    session: Annotated[AsyncSession, TaskiqDepends(session_dependency)] = TaskiqDepends(),
    broker: Annotated[AsyncBroker, TaskiqDepends(broker_dependency)] = TaskiqDepends(),
) -> None:
    """Call this to notify that a particular timestamp within a particular named resource
    has had a batch of inserts/updates/deletes such that requesting all records with that changed_at timestamp
    will yield all resources to be inspected for potentially notifying subscribers

    For deletions - the deleted_time in the archive table will be used

    resource_name: The name of the resource that is being checked for changes
    timestamp: The datetime.timestamp() that will be used for finding resources (must be exact match)"""

    timestamp = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)
    logger.debug("check_db_change_or_delete for resource %s at timestamp %s", resource, timestamp)

    batched_entities = await fetch_batched_entities(session, resource, timestamp)
    for batch in batched_entities:
        await handle_batch(session, batch, href_prefix, broker)
