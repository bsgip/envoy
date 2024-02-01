from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site import Site


async def count_all_sites(session: AsyncSession) -> int:
    """Admin counting of sites - no filtering on aggregator is made"""
    stmt = select(func.count()).select_from(Site)
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_sites(session: AsyncSession, start: int, limit: int) -> Sequence[Site]:
    """Admin selecting of sites - no filtering on aggregator is made"""
    stmt = (
        select(Site)
        .offset(start)
        .limit(limit)
        .order_by(
            Site.site_id.asc(),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()
