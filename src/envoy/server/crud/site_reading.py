from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence, Union, cast

from envoy_schema.server.schema.sep2.types import RoleFlagsType
from sqlalchemy import Select, and_, distinct, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import delete_rows_into_archive
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SITE_READING_TYPE_GROUP_ID_SEQUENCE, SiteReading, SiteReadingType


@dataclass(frozen=True)
class GroupedSiteReadingTypeDetails:
    """We don't model MirrorUsagePoint seperately from MirrorMeterReading - this allows us to roll up
    a group of SiteReadingType instances into something that approximates a MirrorUsagePoint"""

    group_id: int
    group_mrid: str
    site_id: int
    site_lfdi: str
    role_flags: int


async def generate_site_reading_type_group_id(session: AsyncSession) -> int:
    """Creates a new, unique value from the underlying sequence responsible for creating new group ids"""
    return (await session.execute(SITE_READING_TYPE_GROUP_ID_SEQUENCE.next_value())).scalar_one()


async def fetch_site_reading_types_for_group_mrid(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], group_mrid: str
) -> Sequence[SiteReadingType]:
    """Fetches all SiteReadingTypes for the specified group mrid filter conditions

    if site_id is None - it will not be included in the search filter"""
    stmt = select(SiteReadingType).where(
        (SiteReadingType.aggregator_id == aggregator_id) & (SiteReadingType.group_mrid == group_mrid)
    )
    if site_id is not None:
        stmt = stmt.where(SiteReadingType.site_id == site_id)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def fetch_site_reading_types_for_group(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], group_id: int
) -> Sequence[SiteReadingType]:
    """Fetches all SiteReadingTypes for the specified group filter conditions

    if site_id is None - it will not be included in the search filter"""
    stmt = select(SiteReadingType).where(
        (SiteReadingType.aggregator_id == aggregator_id) & (SiteReadingType.group_id == group_id)
    )
    if site_id is not None:
        stmt = stmt.where(SiteReadingType.site_id == site_id)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def fetch_site_reading_type_for_mrid(
    session: AsyncSession, aggregator_id: int, site_id: int, mrid: str
) -> Optional[SiteReadingType]:
    """Fetches the SiteReadingType matched by the specified site scope / mrid. Returns None if not found."""
    stmt = select(SiteReadingType).where(
        (SiteReadingType.aggregator_id == aggregator_id)
        & (SiteReadingType.site_id == site_id)
        & (SiteReadingType.mrid == mrid)
    )

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def _fetch_site_reading_type_groups(
    only_count: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    start: Optional[int],
    changed_after: datetime,
    limit: Optional[int],
) -> Union[int, list[GroupedSiteReadingTypeDetails]]:

    select_clause: Union[Select[tuple[int]], Select[tuple[int, str, int, RoleFlagsType, str]]]
    if only_count:
        select_clause = select(func.count(distinct(SiteReadingType.group_id))).select_from(SiteReadingType)
    else:
        select_clause = select(
            SiteReadingType.group_id,
            func.max(SiteReadingType.group_mrid),
            func.max(SiteReadingType.site_id),
            func.max(SiteReadingType.role_flags),
            func.max(Site.lfdi),
        ).join(Site)

    # Build WHERE clause
    select_clause = select_clause.where(SiteReadingType.aggregator_id == aggregator_id)
    if site_id is not None:
        select_clause = select_clause.where(SiteReadingType.site_id == site_id)
    if changed_after != datetime.min:
        select_clause = select_clause.where(SiteReadingType.changed_time >= changed_after)

    # Make query
    if only_count:
        resp = await session.execute(select_clause)
        return resp.scalar_one()
    else:
        resp = await session.execute(select_clause.limit(limit).offset(start).group_by(SiteReadingType.group_id))
        return [GroupedSiteReadingTypeDetails(row[0], row[1], row[2], row[4], row[3]) for row in resp.tuples().all()]


async def fetch_grouped_site_reading_details(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], start: int, changed_after: datetime, limit: int
) -> list[GroupedSiteReadingTypeDetails]:
    """Fetches a GroupedSiteReadingTypeDetails for each distinct group of SiteReadingType.group_id that match the
    specified filter parameters. Returns the groups ordered by GroupID asc."""
    # Test coverage will enforce the return type
    return cast(
        list[GroupedSiteReadingTypeDetails],
        await _fetch_site_reading_type_groups(False, session, aggregator_id, site_id, start, changed_after, limit),
    )


async def count_grouped_site_reading_details(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], changed_after: datetime
) -> int:
    """Returns the maximal count of values returned by fetch_grouped_site_reading_details (given the same filter)"""
    # Test coverage will enforce the return type
    return cast(
        int,
        await _fetch_site_reading_type_groups(True, session, aggregator_id, site_id, None, changed_after, None),
    )


async def upsert_site_readings(session: AsyncSession, now: datetime, site_readings: list[SiteReading]) -> None:
    """Creates or updates the specified site readings. It's assumed that each SiteReading will have
    been assigned a valid site_reading_type_id before calling this function. No validation will be made for ownership

    Conflicting readings will be deleted (and archived) before being re-inserted.

    now: The current changed_time to mark any updated (deleted and replaced) records with
    site_readings: The readings to insert/update"""

    # Start by deleting all conflicts (archiving them as we go)
    where_clause_and_elements = (
        and_(
            SiteReading.site_reading_type_id == sr.site_reading_type_id,
            SiteReading.time_period_start == sr.time_period_start,
        )
        for sr in site_readings
    )
    or_clause = or_(*where_clause_and_elements)
    await delete_rows_into_archive(session, SiteReading, ArchiveSiteReading, now, lambda q: q.where(or_clause))

    # Now we can do the inserts
    table = SiteReading.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    await session.execute(
        insert(SiteReading).values(([{k: getattr(sr, k) for k in update_cols} for sr in site_readings]))
    )


async def delete_site_reading_type_group(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], group_id: int, deleted_time: datetime
) -> bool:
    """Deletes all site reading types (belonging to aggregator_id/site_id/group) and all descendent FK references. All
    deleted rows will be archived

    aggregator_id: The aggregator ID that this request is scoped to
    site_id: If None - no filtering will be made, otherwise this site_id will be used to check for SRT existence
    group_id: The ID of the SRT's to delete
    deleted_time: The deleted time that will be included in archive records

    Returns True if the site reading types were removed, False otherwise"""

    # Cleanest way of deleting is to validate the site reading types exist for this site and then going wild removing
    # everything related to that record. Not every child record will have access to aggregator_id without a join
    srts = await fetch_site_reading_types_for_group(
        session, aggregator_id=aggregator_id, site_id=site_id, group_id=group_id
    )
    if not srts:
        return False

    srt_ids = [s.site_reading_type_id for s in srts]

    await delete_rows_into_archive(
        session,
        SiteReading,
        ArchiveSiteReading,
        deleted_time,
        lambda q: q.where(SiteReading.site_reading_type_id.in_(srt_ids)),
    )
    await delete_rows_into_archive(
        session,
        SiteReadingType,
        ArchiveSiteReadingType,
        deleted_time,
        lambda q: q.where(SiteReadingType.site_reading_type_id.in_(srt_ids)),
    )

    return True
