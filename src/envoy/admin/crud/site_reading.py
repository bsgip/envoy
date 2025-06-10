from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.site_reading import SiteReading, SiteReadingType


async def count_site_readings_for_site_and_time(
    session: AsyncSession,
    site_id: int,
    start_time: datetime,
    end_time: datetime,
) -> int:
    """Count total site readings for one site within a time range.

    This function counts readings using identical filtering logic as
    select_site_readings_for_site_and_time, providing pagination metadata.

    Args:
        session: Database session
        site_id: site ID to count readings for
        start_time: Inclusive start of time range (compared against time_period_start)
        end_time: Inclusive end of time range (compared against time_period_start)

    Returns:
        Total count of readings matching the criteria

    Note:
        - Uses same filtering logic as select function for consistency
        - No pagination parameters (counts all matching records)
        - Efficient count query without loading actual reading data
    """
    stmt = (
        select(func.count())
        .select_from(SiteReading)
        .join(SiteReadingType)
        .where((SiteReading.time_period_start >= start_time) & (SiteReading.time_period_start <= end_time))
        .where(SiteReadingType.site_id == site_id)
    )

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_site_readings_for_site_and_time(
    session: AsyncSession,
    site_id: int,
    start_time: datetime,
    end_time: datetime,
    start: int = 0,
    limit: int = 1000,
) -> Sequence[SiteReading]:
    """Admin function to retrieve site readings for one site within a time range.

    This function retrieves paginated site readings for a specified site, filtered by time period start.
    The associated SiteReadingType metadata is eagerly loaded for each reading.

    Args:
        session: Database session
        site_id: site ID to query readings for
        start_time: Inclusive start of time range (compared against time_period_start)
        end_time: Inclusive end of time range (compared against time_period_start)
        start: Pagination offset (default: 0)
        limit: Maximum number of readings to return (default: 1000)

    Returns:
        Sequence of SiteReading objects with SiteReadingType relationship loaded,
        ordered by time_period_start ASC

    Notes:
        - No aggregator scoping is applied (admin-level access)
        - Results are ordered by time first, then site_id
        - Eagerly loads SiteReadingType to avoid N+1 queries
    """
    stmt = (
        select(SiteReading)
        .join(SiteReadingType)
        .where((SiteReading.time_period_start >= start_time) & (SiteReading.time_period_start <= end_time))
        .where(SiteReadingType.site_id == site_id)
        .options(selectinload(SiteReading.site_reading_type))
        .order_by(SiteReading.time_period_start.asc())
        .offset(start)
        .limit(limit)
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()
