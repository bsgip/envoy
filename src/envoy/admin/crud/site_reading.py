from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.site_reading import SiteReading, SiteReadingType


async def select_site_readings_for_sites_and_time(
    session: AsyncSession,
    site_ids: list[int],
    start_time: datetime,
    end_time: datetime,
    start: int = 0,
    limit: int = 1000,
) -> Sequence[SiteReading]:
    """Admin function to retrieve site readings for one or more sites within a time range.

    This function retrieves paginated site readings for specified sites, filtered by time period start.
    The associated SiteReadingType metadata is eagerly loaded for each reading.

    Args:
        session: Database session
        site_ids: List of site IDs to query readings for (empty list returns no results)
                 Can be a single site [123] or multiple sites [123, 456, 789]
        start_time: Inclusive start of time range (compared against time_period_start)
        end_time: Inclusive end of time range (compared against time_period_start)
        start: Pagination offset (default: 0)
        limit: Maximum number of readings to return (default: 1000)

    Returns:
        Sequence of SiteReading objects with SiteReadingType relationship loaded,
        ordered by time_period_start ASC, then site_id ASC for consistent pagination

    Notes:
        - No aggregator scoping is applied (admin-level access)
        - Results are ordered by time first, then site_id
        - Large site_ids lists may impact performance - consider batching
    """
    if not site_ids:
        return []

    stmt = (
        select(SiteReading)
        .join(SiteReadingType)
        .where((SiteReading.time_period_start >= start_time) & (SiteReading.time_period_start <= end_time))
        .where(SiteReadingType.site_id.in_(site_ids))
        .options(selectinload(SiteReading.site_reading_type))
        .order_by(SiteReading.time_period_start.asc(), SiteReadingType.site_id.asc())
        .offset(start)
        .limit(limit)
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_site_readings_for_sites_and_time(
    session: AsyncSession,
    site_ids: list[int],
    start_time: datetime,
    end_time: datetime,
) -> int:
    """Count total site readings for one or more sites within a time range.

    This function counts readings using identical filtering logic as
    select_site_readings_for_sites_and_time, providing pagination metadata.

    Args:
        session: Database session
        site_ids: List of site IDs to count readings for (empty list returns 0)
        start_time: Inclusive start of time range (compared against time_period_start)
        end_time: Inclusive end of time range (compared against time_period_start)

    Returns:
        Total count of readings matching the criteria

    Note:
        - Uses same filtering logic as select function for consistency
        - For single site queries, pass [site_id] as a single-item list
        - No pagination parameters (counts all matching records)
        - Efficient count query without loading actual reading data
    """
    if not site_ids:
        return 0

    stmt = (
        select(func.count())
        .select_from(SiteReading)
        .join(SiteReadingType)
        .where((SiteReading.time_period_start >= start_time) & (SiteReading.time_period_start <= end_time))
        .where(SiteReadingType.site_id.in_(site_ids))
    )

    resp = await session.execute(stmt)
    return resp.scalar_one()
