from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from envoy_schema.server.schema.sep2.types import UomType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.tariff import TariffGeneratedRate


@dataclass
class BillingData:
    varh_readings: Sequence[SiteReading]  # Reactive Energy readings
    wh_readings: Sequence[SiteReading]  # Watt Hour readings
    watt_readings: Sequence[SiteReading]  # Watt readings to use a failover if wh_readings are missing
    active_tariffs: Sequence[TariffGeneratedRate]
    active_does: Sequence[DynamicOperatingEnvelope]


async def fetch_billing_data(
    session: AsyncSession, aggregator_id: int, tariff_id: int, period_start: datetime, period_end: datetime
) -> BillingData:
    """Aggregates a bunch of billing related data for a specific time period/aggregator based on entity start times
    (period_start is inclusive, period_end is exclusive). SiteReading will have the SiteReadingType relationship
    populated. All results will be ordered by site_id (ASC) then time (ASC)"""

    tariffs_result = await session.execute(
        select(TariffGeneratedRate)
        .join(Site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id)
            & (Site.aggregator_id == aggregator_id)
            & (TariffGeneratedRate.start_time >= period_start)
            & (TariffGeneratedRate.start_time < period_end)
        )
        .order_by(TariffGeneratedRate.site_id, TariffGeneratedRate.start_time)
    )

    does_result = await session.execute(
        select(DynamicOperatingEnvelope)
        .join(Site)
        .where(
            (Site.aggregator_id == aggregator_id)
            & (DynamicOperatingEnvelope.start_time >= period_start)
            & (DynamicOperatingEnvelope.start_time < period_end)
        )
        .order_by(DynamicOperatingEnvelope.site_id, DynamicOperatingEnvelope.start_time)
    )

    wh_result = await session.execute(
        select(SiteReading)
        .join(SiteReadingType)
        .where(
            (SiteReadingType.aggregator_id == aggregator_id)
            & (SiteReading.time_period_start >= period_start)
            & (SiteReading.time_period_start < period_end)
            & (SiteReadingType.uom == UomType.REAL_ENERGY_WATT_HOURS)
        )
        .options(joinedload(SiteReading.site_reading_type))
        .order_by(SiteReadingType.site_id, SiteReading.time_period_start)
    )

    watt_result = await session.execute(
        select(SiteReading)
        .join(SiteReadingType)
        .where(
            (SiteReadingType.aggregator_id == aggregator_id)
            & (SiteReading.time_period_start >= period_start)
            & (SiteReading.time_period_start < period_end)
            & (SiteReadingType.uom == UomType.REAL_POWER_WATT)
        )
        .options(joinedload(SiteReading.site_reading_type))
        .order_by(SiteReadingType.site_id, SiteReading.time_period_start)
    )

    varh_result = await session.execute(
        select(SiteReading)
        .join(SiteReadingType)
        .where(
            (SiteReadingType.aggregator_id == aggregator_id)
            & (SiteReading.time_period_start >= period_start)
            & (SiteReading.time_period_start < period_end)
            & (SiteReadingType.uom == UomType.REACTIVE_ENERGY_VARH)
        )
        .options(joinedload(SiteReading.site_reading_type))
        .order_by(SiteReadingType.site_id, SiteReading.time_period_start)
    )

    return BillingData(
        active_tariffs=tariffs_result.scalars().all(),
        active_does=does_result.scalars().all(),
        wh_readings=wh_result.scalars().all(),
        varh_readings=varh_result.scalars().all(),
        watt_readings=watt_result.scalars().all(),
    )


async def fetch_aggregator(session: AsyncSession, aggregator_id: int) -> Optional[Aggregator]:
    """Fetches a particular Aggregator by its ID"""
    result = await session.execute(select(Aggregator).where((Aggregator.aggregator_id == aggregator_id)))
    return result.scalar_one_or_none()
