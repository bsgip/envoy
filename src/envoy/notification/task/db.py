from datetime import datetime, timezone
from itertools import islice
from typing import Annotated, Generator, Iterable, Literal, TypeVar, Union, cast

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends, async_shared_broker

from envoy.notification.crud.batch import TResourceModel, fetch_sites_by_changed_at, select_subscriptions_for_resource
from envoy.notification.main import session_dependency
from envoy.notification.task.notification import Notification
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate

T = TypeVar("T")


def batched(iterable: Iterable[T], chunk_size: int) -> Generator[list[T], None, None]:
    """This is a equivalent attempt at implementing the python 3.12 itertools.batched function.

    It splits a sequence of values into chunks of a fixed size, yielding chunks until nothing is left.

    Eg: batched([1,2,3,4,5], 2) will yield the following chunks in an iterator: [1,2] then [3,4] then [5] before
    finishing"""

    iterator = iter(iterable)
    while chunk := list(islice(iterator, chunk_size)):
        yield chunk


def get_primary_key(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the primary key for TResourceModel"""
    if resource == SubscriptionResource.SITE:
        return cast(Site, entity).site_id
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        return cast(DynamicOperatingEnvelope, entity).dynamic_operating_envelope_id
    elif resource == SubscriptionResource.READING:
        return cast(SiteReading, entity).site_reading_type_id
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        return cast(TariffGeneratedRate, entity).tariff_generated_rate_id
    else:
        raise Exception(f"{resource} is unsupported - unable to identify appropriate primary key")


def get_site_id(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the site id for TResourceModel"""
    if resource == SubscriptionResource.SITE:
        return cast(Site, entity).site_id
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        return cast(DynamicOperatingEnvelope, entity).site_id
    elif resource == SubscriptionResource.READING:
        return cast(SiteReading, entity).site_reading_type.site_id
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        return cast(TariffGeneratedRate, entity).site_id
    else:
        raise Exception(f"{resource} is unsupported - unable to identify appropriate site id")


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


@async_shared_broker.task()
async def handle_db_upsert(
    session: Annotated[AsyncSession, TaskiqDepends(session_dependency)],
    resource: SubscriptionResource,
    timestamp_epoch: float,
) -> None:
    """Call this to notify that a particular timestamp within a particular named resource
    has had a batch of inserts/updates such that requesting all records with that changed_at timestamp
    will yield all resources to be inspected for potentially notifying subscribers

    resource_name: The name of the resource that is being checked for changes
    timestamp: The datetime.timestamp() that will be used for finding resources (must be exact match)"""

    timestamp = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)

    if resource == SubscriptionResource.SITE:
        batched_entities = await fetch_sites_by_changed_at(session, timestamp)
    else:
        raise Exception(f"Unsupported resource type: {resource}")

    # Now generate subscription notifications
    all_notifications: list[Notification] = []
    for agg_id, entities in batched_entities.models_by_aggregator_id.items():

        # We enumerate by aggregator ID at the top level (as a way of minimising the size of entities)
        candidate_subscriptions = await select_subscriptions_for_resource(session, agg_id, resource)
        for sub in candidate_subscriptions:
            # Break the entities that apply to this subscription down into "pages" according to
            # the definition of the subscription
            entity_limit = sub.entity_limit if sub.entity_limit > 0 else 1
            entities_to_notify = entities_serviced_by_subscription(sub, resource, entities)
            for entity_page in batched(entities_to_notify, entity_limit):
                all_notifications.append(Notification(entity_page, sub))

    # Finally time to enqueue the outgoing notifications
