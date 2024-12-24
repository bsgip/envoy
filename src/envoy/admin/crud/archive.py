from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate


async def count_archive_sites_for_period(
    session: AsyncSession, period_start: datetime, period_end: datetime, only_deletes: bool
) -> int:
    """Similar to select_archive_sites_for_period - Counts the total number of sites matched by query parameters

    period_start: INCLUSIVE start time to filter archive records by
    period_end: EXCLUSIVE start time to filter archive records by
    only_deletes: If True - filtering will operate on the deleted_time and only records with a non None deleted_time
                  will be considered, otherwise filtering will operate on archive_time and will include everything"""

    stmt = select(func.count()).select_from(ArchiveSite)

    if only_deletes:
        stmt = stmt.where(ArchiveSite.deleted_time >= period_start).where(ArchiveSite.deleted_time < period_end)
    else:
        stmt = stmt.where(ArchiveSite.archive_time >= period_start).where(ArchiveSite.archive_time < period_end)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_archive_sites_for_period(
    session: AsyncSession, start: int, limit: int, period_start: datetime, period_end: datetime, only_deletes: bool
) -> Sequence[ArchiveSite]:
    """Admin selecting of archive sites - no filtering on aggregator is made. Returns ordered by archive_id

    start: How many records to skip
    limit: The maximum number of records to return
    period_start: INCLUSIVE start time to filter archive records by
    period_end: EXCLUSIVE start time to filter archive records by
    only_deletes: If True - filtering will operate on the deleted_time and only records with a non None deleted_time
                  will be considered, otherwise filtering will operate on archive_time and will include everything"""

    stmt = (
        select(ArchiveSite)
        .offset(start)
        .limit(limit)
        .order_by(
            ArchiveSite.archive_id.asc(),
        )
    )

    if only_deletes:
        stmt = stmt.where(ArchiveSite.deleted_time >= period_start).where(ArchiveSite.deleted_time < period_end)
    else:
        stmt = stmt.where(ArchiveSite.archive_time >= period_start).where(ArchiveSite.archive_time < period_end)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_archive_does_for_period(
    session: AsyncSession, period_start: datetime, period_end: datetime, only_deletes: bool
) -> int:
    """Similar to select_archive_does_for_period - Counts the total number of does matched by query parameters

    period_start: INCLUSIVE start time to filter archive records by
    period_end: EXCLUSIVE start time to filter archive records by
    only_deletes: If True - filtering will operate on the deleted_time and only records with a non None deleted_time
                  will be considered, otherwise filtering will operate on archive_time and will include everything"""

    stmt = select(func.count()).select_from(ArchiveDynamicOperatingEnvelope)

    if only_deletes:
        stmt = stmt.where(ArchiveDynamicOperatingEnvelope.deleted_time >= period_start).where(
            ArchiveDynamicOperatingEnvelope.deleted_time < period_end
        )
    else:
        stmt = stmt.where(ArchiveDynamicOperatingEnvelope.archive_time >= period_start).where(
            ArchiveDynamicOperatingEnvelope.archive_time < period_end
        )

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_archive_does_for_period(
    session: AsyncSession, start: int, limit: int, period_start: datetime, period_end: datetime, only_deletes: bool
) -> Sequence[ArchiveDynamicOperatingEnvelope]:
    """Admin selecting of archive does - no filtering on aggregator is made. Returns ordered by archive_id

    start: How many records to skip
    limit: The maximum number of records to return
    period_start: INCLUSIVE start time to filter archive records by
    period_end: EXCLUSIVE start time to filter archive records by
    only_deletes: If True - filtering will operate on the deleted_time and only records with a non None deleted_time
                  will be considered, otherwise filtering will operate on archive_time and will include everything"""

    stmt = (
        select(ArchiveDynamicOperatingEnvelope)
        .offset(start)
        .limit(limit)
        .order_by(
            ArchiveDynamicOperatingEnvelope.archive_id.asc(),
        )
    )

    if only_deletes:
        stmt = stmt.where(ArchiveDynamicOperatingEnvelope.deleted_time >= period_start).where(
            ArchiveDynamicOperatingEnvelope.deleted_time < period_end
        )
    else:
        stmt = stmt.where(ArchiveDynamicOperatingEnvelope.archive_time >= period_start).where(
            ArchiveDynamicOperatingEnvelope.archive_time < period_end
        )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_archive_rates_for_period(
    session: AsyncSession, period_start: datetime, period_end: datetime, only_deletes: bool
) -> int:
    """Similar to select_archive_rates_for_period - Counts the total number of rates matched by query parameters

    period_start: INCLUSIVE start time to filter archive records by
    period_end: EXCLUSIVE start time to filter archive records by
    only_deletes: If True - filtering will operate on the deleted_time and only records with a non None deleted_time
                  will be considered, otherwise filtering will operate on archive_time and will include everything"""

    stmt = select(func.count()).select_from(ArchiveTariffGeneratedRate)

    if only_deletes:
        stmt = stmt.where(ArchiveTariffGeneratedRate.deleted_time >= period_start).where(
            ArchiveTariffGeneratedRate.deleted_time < period_end
        )
    else:
        stmt = stmt.where(ArchiveTariffGeneratedRate.archive_time >= period_start).where(
            ArchiveTariffGeneratedRate.archive_time < period_end
        )

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_archive_rates_for_period(
    session: AsyncSession, start: int, limit: int, period_start: datetime, period_end: datetime, only_deletes: bool
) -> Sequence[ArchiveTariffGeneratedRate]:
    """Admin selecting of archive rates - no filtering on aggregator is made. Returns ordered by archive_id

    start: How many records to skip
    limit: The maximum number of records to return
    period_start: INCLUSIVE start time to filter archive records by
    period_end: EXCLUSIVE start time to filter archive records by
    only_deletes: If True - filtering will operate on the deleted_time and only records with a non None deleted_time
                  will be considered, otherwise filtering will operate on archive_time and will include everything"""

    stmt = (
        select(ArchiveTariffGeneratedRate)
        .offset(start)
        .limit(limit)
        .order_by(
            ArchiveTariffGeneratedRate.archive_id.asc(),
        )
    )

    if only_deletes:
        stmt = stmt.where(ArchiveTariffGeneratedRate.deleted_time >= period_start).where(
            ArchiveTariffGeneratedRate.deleted_time < period_end
        )
    else:
        stmt = stmt.where(ArchiveTariffGeneratedRate.archive_time >= period_start).where(
            ArchiveTariffGeneratedRate.archive_time < period_end
        )

    resp = await session.execute(stmt)
    return resp.scalars().all()
