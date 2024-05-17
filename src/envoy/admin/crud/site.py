from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.site import Site, SiteGroup, SiteGroupAssignment


async def count_all_sites(session: AsyncSession, group_filter: Optional[str]) -> int:
    """Admin counting of sites - no filtering on aggregator is made"""
    stmt = select(func.count()).select_from(Site)

    if group_filter:
        stmt = stmt.join(SiteGroupAssignment).join(SiteGroup).where(SiteGroup.name == group_filter)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_sites(
    session: AsyncSession, group_filter: Optional[str], start: int, limit: int, include_groups: bool = False
) -> Sequence[Site]:
    """Admin selecting of sites - no filtering on aggregator is made"""

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

    if group_filter:
        stmt = stmt.join(SiteGroupAssignment).join(SiteGroup).where(SiteGroup.name == group_filter)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_all_site_groups(session: AsyncSession) -> int:
    """Admin counting of site groups"""
    stmt = select(func.count()).select_from(SiteGroup)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_site_groups(
    session: AsyncSession, group_filter: Optional[str], start: int, limit: int
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
