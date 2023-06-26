from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.site import count_all_sites, select_all_sites
from envoy.admin.mapper.site import SiteMapper
from envoy.admin.schema.site import SitePageResponse


class SiteManager:
    @staticmethod
    async def get_all_sites(session: AsyncSession, start: int, limit: int) -> SitePageResponse:
        """Admin specific (paginated) fetch of sites that covers all aggregators"""
        site_count = await count_all_sites(session)
        sites = await select_all_sites(session, start=start, limit=limit)
        return SiteMapper.map_to_response(total_count=site_count, limit=limit, start=start, sites=sites)
