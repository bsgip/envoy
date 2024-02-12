from datetime import datetime
from typing import Generic, Sequence, TypeVar, Union, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.notification.exception import NotificationError
from envoy.server.crud.common import localize_start_time
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate

TResourceModel = TypeVar(
    "TResourceModel", bound=Union[Site, DynamicOperatingEnvelope, TariffGeneratedRate, SiteReading]
)


class AggregatorBatchedEntities(Generic[TResourceModel]):
    """A set of TResourceModel entities keyed by their aggregator ID and then site id"""

    timestamp: datetime
    models_by_batch_key: dict[tuple, list[TResourceModel]]  # First element of batch key will be aggregator_id
    total_entities: int

    def __init__(self, timestamp: datetime, resource: SubscriptionResource, models: Sequence[TResourceModel]) -> None:
        super().__init__()

        self.timestamp = timestamp

        self.models_by_batch_key = {}
        self.total_entities = 0
        for m in models:
            self.total_entities = self.total_entities + 1
            batch_key = get_batch_key(resource, m)

            model_list = self.models_by_batch_key.get(batch_key, None)
            if model_list is None:
                self.models_by_batch_key[batch_key] = [m]
            else:
                model_list.append(m)


def get_batch_key(resource: SubscriptionResource, entity: TResourceModel) -> tuple:
    """
    Gets a multipart key in the form of a tuple that describes entity as a single sep2 resource. This is because
    sep2 Notifications are only sent out underneath a single resource (eg /edev/3/derp/doe/derc/1) which means all
    notifications we generate MUST be grouped by this batch key

    NOTE - the first element of every tuple will be aggregator_id

    Given the SubscriptionResource - it's safe to rely on the ordering of the batch key tuple entries:

    SubscriptionResource.SITE: (aggregator_id: int, site_id: int)
    SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE: (aggregator_id: int, site_id: int)
    SubscriptionResource.READING: (aggregator_id: int, site_id: int, site_reading_type_id: int)
    SubscriptionResource.TARIFF_GENERATED_RATE: (aggregator_id: int, tariff_id: int, site_id: int, day: date)
    """
    if resource == SubscriptionResource.SITE:
        site = cast(Site, entity)
        return (site.aggregator_id, site.site_id)
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        doe = cast(DynamicOperatingEnvelope, entity)
        return (doe.site.aggregator_id, doe.site_id)
    elif resource == SubscriptionResource.READING:
        reading = cast(SiteReading, entity)
        return (
            reading.site_reading_type.aggregator_id,
            reading.site_reading_type.site_id,
            reading.site_reading_type.site_reading_type_id,
        )
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        rate = cast(TariffGeneratedRate, entity)
        return (rate.site.aggregator_id, rate.tariff_id, rate.site_id, rate.start_time.date())
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate batch key")


def get_subscription_filter_id(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the "subscription filter" id for TResourceModel. This is the field
    that Subscription.resource_id will filter on (if specified). This practically allows subscriptions
    to apply to only a subset of entities"""
    if resource == SubscriptionResource.SITE:
        # Site lists subscriptions can be scoped to a single site
        return cast(Site, entity).site_id
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        # DOE subscriptions can be scoped to a single DOE (doesn't make a lot of sense in practice but it can be done)
        return cast(DynamicOperatingEnvelope, entity).dynamic_operating_envelope_id
    elif resource == SubscriptionResource.READING:
        # Reading subscriptions can be scoped to the overarching type
        return cast(SiteReading, entity).site_reading_type_id
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        # rate subscriptions can be scoped to a single tariff
        return cast(TariffGeneratedRate, entity).tariff_id
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate primary key")


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
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate site id")


async def select_subscriptions_for_resource(
    session: AsyncSession, aggregator_id: int, resource: SubscriptionResource
) -> Sequence[Subscription]:
    """Fetches all subscriptions that 'might' match a change in a particular resource. Actual checks will not be made.

    Will populate the Subscription.conditions relationship"""

    stmt = (
        select(Subscription)
        .where((Subscription.aggregator_id == aggregator_id) & (Subscription.resource_type == resource))
        .options(selectinload(Subscription.conditions))
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def fetch_sites_by_changed_at(session: AsyncSession, timestamp: datetime) -> AggregatorBatchedEntities[Site]:
    """Fetches all sites matching the specified changed_at and returns them keyed by their aggregator/site id"""

    stmt = select(Site).where(Site.changed_time == timestamp)
    resp = await session.execute(stmt)
    return AggregatorBatchedEntities(timestamp, SubscriptionResource.SITE, resp.scalars().all())


async def fetch_rates_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[TariffGeneratedRate]:
    """Fetches all rates matching the specified changed_at and returns them keyed by their aggregator/site id

    Will include the TariffGeneratedRate.site relationship"""

    stmt = (
        select(TariffGeneratedRate, Site.timezone_id)
        .join(TariffGeneratedRate.site)
        .where(TariffGeneratedRate.changed_time == timestamp)
        .options(selectinload(TariffGeneratedRate.site))
    )
    resp = await session.execute(stmt)
    return AggregatorBatchedEntities(
        timestamp,
        SubscriptionResource.TARIFF_GENERATED_RATE,
        [localize_start_time(rate_and_tz) for rate_and_tz in resp.all()],
    )


async def fetch_does_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[DynamicOperatingEnvelope]:
    """Fetches all DOEs matching the specified changed_at and returns them keyed by their aggregator/site id

    Will include the DynamicOperatingEnvelope.site relationship"""

    stmt = (
        select(DynamicOperatingEnvelope, Site.timezone_id)
        .join(DynamicOperatingEnvelope.site)
        .where(DynamicOperatingEnvelope.changed_time == timestamp)
        .options(selectinload(DynamicOperatingEnvelope.site))
    )
    resp = await session.execute(stmt)

    return AggregatorBatchedEntities(
        timestamp,
        SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
        [localize_start_time(doe_and_tz) for doe_and_tz in resp.all()],
    )


async def fetch_readings_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteReading]:
    """Fetches all site readings matching the specified changed_at and returns them keyed by their aggregator/site id

    Will include the SiteReading.site_reading_type relationship"""

    stmt = (
        select(SiteReading)
        .join(SiteReading.site_reading_type)
        .where(SiteReading.changed_time == timestamp)
        .options(selectinload(SiteReading.site_reading_type))
    )
    resp = await session.execute(stmt)
    return AggregatorBatchedEntities(timestamp, SubscriptionResource.READING, resp.scalars().all())
