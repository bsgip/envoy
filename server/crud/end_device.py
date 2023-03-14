from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.model.site import Site


async def select_all_sites_with_aggregator_id(
    session: AsyncSession, aggregator_id: int
) -> list[Site]:
    """TODO"""
    stmt = select(
        Site.site_id, Site.lfdi, Site.sfdi, Site.changed_time, Site.device_category
    ).where(Site.aggregator_id == aggregator_id)

    resp = await session.execute(stmt)

    return resp.all()


async def select_single_site_with_site_id(
    session: AsyncSession, site_id, aggregator_id: int
) -> Optional[Site]:
    """Site and aggregator id need to be used to make sure the aggregator owns this site."""
    stmt = select(
        Site.site_id, Site.lfdi, Site.sfdi, Site.changed_time, Site.device_category
    ).where((Site.aggregator_id == aggregator_id) & (Site.site_id == site_id))

    resp = await session.execute(stmt)

    return resp.scalar_one_or_none()
