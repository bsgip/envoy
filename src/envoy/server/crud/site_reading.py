from datetime import datetime
from typing import Optional, Sequence, Union

from sqlalchemy import Select, and_, func, insert, or_, select
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType


async def fetch_site_reading_type_for_aggregator(
    session: AsyncSession,
    aggregator_id: int,
    site_reading_type_id: int,
    site_id: Optional[int],
    include_site_relation: bool,
) -> Optional[SiteReadingType]:
    """Fetches the SiteReadingType by ID (also validating aggregator_id) - returns None if it can't be found.

    if site_id is specified - An additional filter on site_id will be applied to the lookup

    if include_site_relation is True - the site relation will also be populated (defaults to raise otherwise)
    """
    stmt = select(SiteReadingType).where(
        (SiteReadingType.site_reading_type_id == site_reading_type_id)
        & (SiteReadingType.aggregator_id == aggregator_id)
    )

    if site_id is not None:
        stmt = stmt.where(SiteReadingType.site_id == site_id)

    if include_site_relation:
        stmt = stmt.options(selectinload(SiteReadingType.site))

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def _site_reading_types_for_aggregator(
    only_count: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[SiteReadingType], int]:
    """Internal utility for making site_reading_types_for_aggregator  requests that either counts the entities or
    returns a page of the entities

    if site_id is specified - An additional filter on site_id will be applied to the lookup

    Orders by sep2 requirements on MirrorUsagePoint which is id DESC"""

    select_clause: Union[Select[tuple[int]], Select[tuple[SiteReadingType]]]
    if only_count:
        select_clause = select(func.count()).select_from(SiteReadingType)
    else:
        select_clause = select(SiteReadingType)

    stmt = (
        select_clause.join(Site)
        .where(
            (SiteReadingType.aggregator_id == aggregator_id)
            & (SiteReadingType.changed_time >= changed_after)
            & (Site.aggregator_id == aggregator_id)  # Only fetch sites that are currently assigned to this aggregator
        )
        .offset(start)
        .limit(limit)
    )

    if site_id is not None:
        stmt = stmt.where(SiteReadingType.site_id == site_id)

    if not only_count:
        stmt = stmt.options(selectinload(SiteReadingType.site)).order_by(
            SiteReadingType.site_reading_type_id.desc(),
        )

    resp = await session.execute(stmt)
    if only_count:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def fetch_site_reading_types_page_for_aggregator(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    start: int,
    limit: int,
    changed_after: datetime,
) -> Sequence[SiteReadingType]:
    """Fetches a page of SiteReadingType for a particular aggregator_id. The SiteReadingType will have the
    reference Site included"""
    return await _site_reading_types_for_aggregator(
        False,
        session,
        aggregator_id=aggregator_id,
        site_id=site_id,
        start=start,
        limit=limit,
        changed_after=changed_after,
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def count_site_reading_types_for_aggregator(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    changed_after: datetime,
) -> int:
    """Fetches a page of SiteReadingType for a particular aggregator_id"""
    return await _site_reading_types_for_aggregator(
        True, session, aggregator_id=aggregator_id, site_id=site_id, start=0, limit=None, changed_after=changed_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def upsert_site_reading_type_for_aggregator(
    session: AsyncSession, aggregator_id: int, site_reading_type: SiteReadingType
) -> int:
    """Creates or updates the specified site reading type. If site's aggregator_id doesn't match aggregator_id then
    this will raise an error without modifying the DB. Returns the site_reading_type_id of the inserted/existing site

    The current value (if any) for the SiteReadingType will be archived

    Returns the site_reading_type_id of the created/updated SiteReadingType"""

    if aggregator_id != site_reading_type.aggregator_id:
        raise ValueError(
            f"Specified aggregator_id {aggregator_id} mismatches site.aggregator_id {site_reading_type.aggregator_id}"
        )

    # "Save" any existing records with the same data to the archive table
    await copy_rows_into_archive(
        session,
        SiteReadingType,
        ArchiveSiteReadingType,
        lambda q: q.where(
            (SiteReadingType.aggregator_id == aggregator_id)
            & (SiteReadingType.site_id == site_reading_type.site_id)
            & (SiteReadingType.uom == site_reading_type.uom)
            & (SiteReadingType.data_qualifier == site_reading_type.data_qualifier)
            & (SiteReadingType.flow_direction == site_reading_type.flow_direction)
            & (SiteReadingType.accumulation_behaviour == site_reading_type.accumulation_behaviour)
            & (SiteReadingType.kind == site_reading_type.kind)
            & (SiteReadingType.phase == site_reading_type.phase)
            & (SiteReadingType.power_of_ten_multiplier == site_reading_type.power_of_ten_multiplier)
            & (SiteReadingType.default_interval_seconds == site_reading_type.default_interval_seconds)
            & (SiteReadingType.role_flags == site_reading_type.role_flags)
        ),
    )

    # Perform the upsert
    table = SiteReadingType.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    stmt = psql_insert(SiteReadingType).values(**{k: getattr(site_reading_type, k) for k in update_cols})

    resp = await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[
                SiteReadingType.aggregator_id,
                SiteReadingType.site_id,
                SiteReadingType.uom,
                SiteReadingType.data_qualifier,
                SiteReadingType.flow_direction,
                SiteReadingType.accumulation_behaviour,
                SiteReadingType.kind,
                SiteReadingType.phase,
                SiteReadingType.power_of_ten_multiplier,
                SiteReadingType.default_interval_seconds,
                SiteReadingType.role_flags,
            ],
            set_={k: getattr(stmt.excluded, k) for k in update_cols},
        ).returning(SiteReadingType.site_reading_type_id)
    )
    return resp.scalar_one()


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


async def delete_site_reading_type_for_aggregator(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], site_reading_type_id: int, deleted_time: datetime
) -> bool:
    """Delete the specified site reading type (belonging to aggregator_id/site_id) and all descendent FK references. All
    deleted rows will be archived

    aggregator_id: The aggregator ID that this request is scoped to
    site_id: If None - no filtering will be made, otherwise this site_id will be used to check for SRT existence
    site_reading_type_id: The ID of the SRT to delete
    deleted_time: The deleted time that will be included in archive records

    Returns True if the site reading type was removed, False otherwise"""

    # Cleanest way of deleting is to validate the site reading type exists for this site and then going wild removing
    # everything related to that record. Not every child record will have access to aggregator_id without a join
    srt = await fetch_site_reading_type_for_aggregator(
        session,
        site_id=site_id,
        aggregator_id=aggregator_id,
        site_reading_type_id=site_reading_type_id,
        include_site_relation=False,
    )
    if srt is None:
        return False

    await delete_rows_into_archive(
        session,
        SiteReading,
        ArchiveSiteReading,
        deleted_time,
        lambda q: q.where(SiteReading.site_reading_type_id == site_reading_type_id),
    )
    await delete_rows_into_archive(
        session,
        SiteReadingType,
        ArchiveSiteReadingType,
        deleted_time,
        lambda q: q.where(SiteReadingType.site_reading_type_id == site_reading_type_id),
    )

    return True
