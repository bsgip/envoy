from datetime import datetime
from typing import Optional

from envoy_schema.admin.schema.site import SitePageResponse, SiteResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.site import (
    count_all_site_groups,
    count_all_sites,
    select_all_site_groups,
    select_all_sites,
    select_single_site_no_scoping,
)
from envoy.admin.mapper.site import SiteGroupMapper, SiteMapper
from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.end_device import delete_site_for_aggregator
from envoy.server.manager.time import utc_now
from envoy.server.model.subscription import SubscriptionResource


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
    async def get_single_site(session: AsyncSession, site_id: int) -> Optional[SiteResponse]:
        """Admin specific fetch of a single site that covers all aggregators."""
        site = await select_single_site_no_scoping(session, site_id, include_der=True, include_groups=True)
        if site is None:
            return None

        return SiteMapper.map_to_site_response(site)

    @staticmethod
    async def delete_single_site(session: AsyncSession, site_id: int) -> bool:
        """Admin specific delete of a single site."""

        site = await select_single_site_no_scoping(session, site_id, include_der=False, include_groups=False)
        if site is None:
            return False

        deleted_time = utc_now()
        is_deleted = await delete_site_for_aggregator(session, site.aggregator_id, site_id, deleted_time)

        await session.commit()
        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE, deleted_time)

        return is_deleted

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
