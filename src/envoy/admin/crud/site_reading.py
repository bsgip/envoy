from datetime import datetime
from typing import Sequence
from envoy_schema.server.schema.sep2.types import UomType
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy_schema.server.schema.sep2.types import DataQualifierType, KindType


async def count_site_readings_for_site_and_time(
    session: AsyncSession,
    site_type_ids: Sequence[int],
    start_time: datetime,
    end_time: datetime,
) -> int:
    """Count total site readings for a sequence of site_type_ids within a time range."""

    # Return 0 immediately if no site_type_ids provided
    if not site_type_ids:
        return 0

    stmt = (
        select(func.count(SiteReading.site_reading_id))
        .where(SiteReading.site_reading_type_id.in_(site_type_ids))
        .where(SiteReading.time_period_start >= start_time)
        .where(SiteReading.time_period_start < end_time)
    )

    resp = await session.execute(stmt)
    return resp.scalar() or 0


async def select_csip_aus_site_type_ids(
    session: AsyncSession,
    aggregator_id: int,
    site_id: int,
    uom: UomType,
) -> Sequence[int]:
    """Function to obtain reading_types for a site given a site and aggregator id"""

    stmt = (
        select(SiteReadingType.site_reading_type_id)
        .where(SiteReadingType.aggregator_id == aggregator_id)
        .where(SiteReadingType.site_id == site_id)
        .where(SiteReadingType.uom == uom.value)
        .where(SiteReadingType.data_qualifier.in_([DataQualifierType.AVERAGE, DataQualifierType.NOT_APPLICABLE]))
        .where(SiteReadingType.kind.in_([KindType.POWER, KindType.NOT_APPLICABLE]))
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_site_readings_for_site_and_time(
    session: AsyncSession,
    site_type_ids: Sequence[int],
    start_time: datetime,
    end_time: datetime,
    start: int = 0,
    limit: int = 500,
) -> Sequence[SiteReading]:
    """Admin function to retrieve site readings for a sequence of site_type_ids within a time range."""

    # Return empty list immediately if no site_type_ids provided
    if not site_type_ids:
        return []

    stmt = (
        select(SiteReading)
        .where(SiteReading.site_reading_type_id.in_(site_type_ids))
        .where(SiteReading.time_period_start >= start_time)
        .where(SiteReading.time_period_start < end_time)
        .options(selectinload(SiteReading.site_reading_type))
        .order_by(SiteReading.time_period_start.asc())
        .offset(start)
        .limit(limit)
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()
