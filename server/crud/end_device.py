from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.model.site import Site


async def get_all_sites_with_aggregator_id(session: AsyncSession, aggregator_id: int):
    stmt = select(
        Site.site_id, Site.lfdi, Site.sfdi, Site.changed_time, Site.device_category
    ).where(Site.aggregator_id == aggregator_id)

    resp = await session.execute(stmt)

    return resp.all()
