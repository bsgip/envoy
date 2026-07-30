from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.site import Site, SiteGroup, SiteGroupAssignment


async def count_all_sites(
    session: AsyncSession,
    group_filter: str | None,
    changed_after: datetime | None,
    nmi_filter: str | None = None,
    aggregator_id_filter: int | None = None,
) -> int:
    """Admin counting of sites - no filtering on aggregator is made. If changed_after is specified, only
    sites that have their changed_time >= changed_after will be included"""
    stmt = select(func.count()).select_from(Site)

    if group_filter:
        stmt = stmt.join(SiteGroupAssignment).join(SiteGroup).where(SiteGroup.name == group_filter)

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(Site.changed_time >= changed_after)

    if nmi_filter:
        stmt = stmt.where(Site.nmi == nmi_filter)

    if aggregator_id_filter is not None:
        stmt = stmt.where(Site.aggregator_id == aggregator_id_filter)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_sites(
    session: AsyncSession,
    group_filter: str | None,
    start: int,
    limit: int,
    changed_after: datetime | None,
    include_groups: bool = False,
    include_der: bool = False,
    nmi_filter: str | None = None,
    aggregator_id_filter: int | None = None,
) -> Sequence[Site]:
    """Admin selecting of sites - no filtering on aggregator is made."""

    stmt = (
        select(Site)
        .offset(start)
        .limit(limit)
        .order_by(
            Site.site_id.asc(),
        )
    )

    if include_groups:
        stmt = stmt.options(selectinload(Site.assignments).selectinload(SiteGroupAssignment.group))

    if include_der:
        stmt = stmt.options(
            selectinload(Site.site_der_availability),
            selectinload(Site.site_der_rating),
            selectinload(Site.site_der_setting),
            selectinload(Site.site_der_status),
        )

    if group_filter:
        stmt = stmt.join(SiteGroupAssignment).join(SiteGroup).where(SiteGroup.name == group_filter)

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(Site.changed_time >= changed_after)

    if nmi_filter:
        stmt = stmt.where(Site.nmi == nmi_filter)

    if aggregator_id_filter is not None:
        stmt = stmt.where(Site.aggregator_id == aggregator_id_filter)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_all_site_groups(session: AsyncSession) -> int:
    """Admin counting of site groups"""
    stmt = select(func.count()).select_from(SiteGroup)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_site_groups(
    session: AsyncSession, group_filter: str | None, start: int, limit: int
) -> list[tuple[SiteGroup, int]]:
    """Admin selecting of groups - returns a tuple with the count of linked sites"""

    stmt = (
        select(SiteGroup)
        .offset(start)
        .limit(limit)
        .order_by(
            SiteGroup.site_group_id.asc(),
        )
    )

    if group_filter:
        stmt = stmt.where(SiteGroup.name == group_filter)

    resp = await session.execute(stmt)
    groups = resp.scalars().all()
    group_ids = [g.site_group_id for g in groups]

    # now fetch counts for the selected groups
    count_stmt = (
        select(SiteGroupAssignment.site_group_id, func.count())
        .select_from(SiteGroupAssignment)
        .group_by(SiteGroupAssignment.site_group_id)
        .where(SiteGroupAssignment.site_group_id.in_(group_ids))
    )

    count_resp = await session.execute(count_stmt)
    count_by_group_id: dict[int, int] = {}
    for group_id, count in count_resp.all():
        count_by_group_id[group_id] = count

    # pair it all up
    results: list[tuple[SiteGroup, int]] = []
    for group in groups:
        results.append((group, count_by_group_id.get(group.site_group_id, 0)))

    return results


async def select_site_group_by_name(session: AsyncSession, group_name: str) -> SiteGroup | None:
    """Admin selecting of a single SiteGroup by its unique name"""

    stmt = select(SiteGroup).where(SiteGroup.name == group_name)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def count_all_site_group_assignments(session: AsyncSession, site_group_id: int) -> int:
    """Admin counting of SiteGroupAssignments belonging to a single SiteGroup"""
    stmt = (
        select(func.count()).select_from(SiteGroupAssignment).where(SiteGroupAssignment.site_group_id == site_group_id)
    )

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_site_group_assignments(
    session: AsyncSession, site_group_id: int, start: int, limit: int
) -> Sequence[SiteGroupAssignment]:
    """Admin selecting of SiteGroupAssignments belonging to a single SiteGroup"""

    stmt = (
        select(SiteGroupAssignment)
        .where(SiteGroupAssignment.site_group_id == site_group_id)
        .offset(start)
        .limit(limit)
        .order_by(
            SiteGroupAssignment.site_group_assignment_id.asc(),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_single_site_group_assignment(
    session: AsyncSession, site_group_id: int, site_group_assignment_id: int
) -> SiteGroupAssignment | None:
    """Admin selecting of a single SiteGroupAssignment, scoped to a specific SiteGroup"""

    stmt = select(SiteGroupAssignment).where(
        SiteGroupAssignment.site_group_id == site_group_id,
        SiteGroupAssignment.site_group_assignment_id == site_group_assignment_id,
    )

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_single_site_no_scoping(
    session: AsyncSession,
    site_id: int,
    include_groups: bool = False,
    include_der: bool = False,
) -> Site | None:
    """Admin selecting of a single site - no filtering on aggregator is made."""

    stmt = select(Site).limit(1).where(Site.site_id == site_id)

    if include_groups:
        stmt = stmt.options(selectinload(Site.assignments).selectinload(SiteGroupAssignment.group))

    if include_der:
        stmt = stmt.options(
            selectinload(Site.site_der_availability),
            selectinload(Site.site_der_rating),
            selectinload(Site.site_der_setting),
            selectinload(Site.site_der_status),
        )

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()
