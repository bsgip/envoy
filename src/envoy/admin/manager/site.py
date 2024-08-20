from datetime import datetime
from typing import Optional

from envoy_schema.admin.schema.site import SitePageResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.site import count_all_site_groups, count_all_sites, select_all_site_groups, select_all_sites
from envoy.admin.mapper.site import SiteGroupMapper, SiteMapper


class SiteManager:
    @staticmethod
    async def get_all_sites(
        session: AsyncSession, start: int, limit: int, group_filter: Optional[str], changed_after: Optional[datetime]
    ) -> SitePageResponse:
        """Admin specific (paginated) fetch of sites that covers all aggregators.
        group_filter: If specified - filter to sites that belong to a group with this name
        changed_after: If specified - filter to sites whose changed date is >= this value"""
        site_count = await count_all_sites(session, group_filter, changed_after)
        sites = await select_all_sites(
            session,
            group_filter=group_filter,
            changed_after=changed_after,
            start=start,
            limit=limit,
            include_groups=True,
            include_der=True,
        )
        return SiteMapper.map_to_response(
            total_count=site_count,
            limit=limit,
            start=start,
            group=group_filter,
            after=changed_after,
            sites=sites,
        )

    @staticmethod
    async def get_all_site_groups(session: AsyncSession, start: int, limit: int) -> SiteGroupPageResponse:
        """Admin specific (paginated) fetch of site groups that covers all aggregators."""
        group_count = await count_all_site_groups(session)
        groups = await select_all_site_groups(session, group_filter=None, start=start, limit=limit)
        return SiteGroupMapper.map_to_response(
            total_count=group_count, limit=limit, start=start, site_groups_with_count=groups
        )

    @staticmethod
    async def get_all_site_group_by_name(session: AsyncSession, group_name: str) -> Optional[SiteGroupResponse]:
        """Admin specific (paginated) fetch of a specific site group by name."""
        groups = await select_all_site_groups(session, group_filter=group_name, start=0, limit=1)
        if len(groups) > 0:
            return SiteGroupMapper.map_to_site_group_response(groups[0][0], groups[0][1])
        return None
