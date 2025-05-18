from datetime import datetime
from typing import Callable, Optional, Sequence

from sqlalchemy import Delete, and_, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import delete_rows_into_archive
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup


async def delete_does_with_start_time_in_range(
    session: AsyncSession,
    site_control_group_id: int,
    site_id: Optional[int],
    period_start: datetime,
    period_end: datetime,
    deleted_time: datetime,
) -> None:
    """Deletes (with archive) all does whose **start_time** is in the range period_start to period_end. Does not perform
    any checks for aggregator_id scoping

    site_control_group_id: Only this site control group's controls will be considered
    site_id: if specified - scope the deletion to just controls for this site
    period_start: inclusive start of range to search
    period_end: exclusive end of range to search"""

    query: Callable[[Delete], Delete]
    if site_id is None:
        query = lambda q: q.where(  # noqa: E731
            (DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
            & (DynamicOperatingEnvelope.start_time >= period_start)
            & (DynamicOperatingEnvelope.start_time < period_end)
        )
    else:
        query = lambda q: q.where(  # noqa: E731
            (DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
            & (DynamicOperatingEnvelope.site_id == site_id)
            & (DynamicOperatingEnvelope.start_time >= period_start)
            & (DynamicOperatingEnvelope.start_time < period_end)
        )

    # Perform the archival delete
    await delete_rows_into_archive(
        session, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, deleted_time, query
    )


async def upsert_many_doe(
    session: AsyncSession, doe_list: list[DynamicOperatingEnvelope], deleted_time: datetime
) -> None:
    """Adds a multiple DynamicOperatingEnvelope into the db. If any DOE conflict on site/start time, those
    conflicts will first be archived and then the new DOE values will take their place"""

    # Start by deleting all conflicts (archiving them as we go)
    where_clause_and_elements = (
        and_(
            DynamicOperatingEnvelope.site_id == doe.site_id,
            DynamicOperatingEnvelope.start_time == doe.start_time,
        )
        for doe in doe_list
    )
    or_clause = or_(*where_clause_and_elements)
    await delete_rows_into_archive(
        session, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, deleted_time, lambda q: q.where(or_clause)
    )

    # Now we can do the inserts
    table = DynamicOperatingEnvelope.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    await session.execute(
        insert(DynamicOperatingEnvelope).values(([{k: getattr(doe, k) for k in update_cols} for doe in doe_list]))
    )


async def count_all_does(session: AsyncSession, site_control_group_id: int, changed_after: Optional[datetime]) -> int:
    """Admin counting of does - no filtering on aggregator is made. If changed_after is specified, only
    does that have their changed_time >= changed_after will be included"""
    stmt = (
        select(func.count())
        .select_from(DynamicOperatingEnvelope)
        .where(DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
    )

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(DynamicOperatingEnvelope.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_does(
    session: AsyncSession,
    site_control_group_id: int,
    start: int,
    limit: int,
    changed_after: Optional[datetime],
) -> Sequence[DynamicOperatingEnvelope]:
    """Admin selecting of does - no filtering on aggregator is made. Returns ordered by dynamic_operating_envelope_id

    changed_after is INCLUSIVE"""

    stmt = (
        select(DynamicOperatingEnvelope)
        .offset(start)
        .limit(limit)
        .where(DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
        .order_by(
            DynamicOperatingEnvelope.dynamic_operating_envelope_id.asc(),
        )
    )

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(DynamicOperatingEnvelope.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_all_site_control_groups(session: AsyncSession, changed_after: Optional[datetime]) -> int:
    """Admin counting of site control groups. If changed_after is specified, only groups that have their
    changed_time >= changed_after will be included"""
    stmt = select(func.count()).select_from(SiteControlGroup)

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(SiteControlGroup.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_site_control_groups(
    session: AsyncSession,
    start: int,
    limit: int,
    changed_after: Optional[datetime],
) -> Sequence[SiteControlGroup]:
    """Admin selecting of site control groups - no filtering on aggregator is made. Returns ordered by
    site_control_group_id ASC

    changed_after is INCLUSIVE"""

    stmt = (
        select(SiteControlGroup)
        .offset(start)
        .limit(limit)
        .order_by(
            SiteControlGroup.site_control_group_id.asc(),
        )
    )

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(SiteControlGroup.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalars().all()
