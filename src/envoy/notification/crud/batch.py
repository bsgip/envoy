from datetime import datetime
from typing import Generic, Optional, Sequence, TypeVar, Union, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    models_by_aggregator_then_site_id: dict[int, dict[int, list[TResourceModel]]]

    def __init__(self, timestamp: datetime, resource: SubscriptionResource, models: Sequence[TResourceModel]) -> None:
        super().__init__()

        self.timestamp = timestamp

        self.models_by_aggregator_then_site_id = {}
        for m in models:
            agg_id = get_aggregator_id(resource, m)
            site_id = get_site_id(resource, m)

            site_dict = self.models_by_aggregator_then_site_id.get(agg_id, None)
            if site_dict is None:
                self.models_by_aggregator_then_site_id[agg_id] = {site_id: [m]}
            else:
                model_list = site_dict.get(site_id, None)
                if model_list is None:
                    site_dict[site_id] = [m]
                else:
                    model_list.append(m)


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


def get_aggregator_id(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the aggregator id for TResourceModel"""
    if resource == SubscriptionResource.SITE:
        return cast(Site, entity).aggregator_id
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        return cast(DynamicOperatingEnvelope, entity).site.aggregator_id
    elif resource == SubscriptionResource.READING:
        return cast(SiteReading, entity).site_reading_type.aggregator_id
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        return cast(TariffGeneratedRate, entity).site.aggregator_id
    else:
        raise Exception(f"{resource} is unsupported - unable to identify appropriate aggregator id")


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
        .where(SiteReading.changed_time == timestamp)
        .options(selectinload(SiteReading.site_reading_type))
    )
    resp = await session.execute(stmt)
    return AggregatorBatchedEntities(timestamp, SubscriptionResource.READING, resp.scalars().all())
