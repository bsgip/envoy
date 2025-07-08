from datetime import datetime
from typing import Optional

from envoy_schema.admin.schema.site_control import (
    SiteControlGroupPageResponse,
    SiteControlGroupRequest,
    SiteControlGroupResponse,
    SiteControlPageResponse,
    SiteControlRequest,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.doe import (
    count_all_does,
    count_all_site_control_groups,
    delete_does_with_start_time_in_range,
    select_all_does,
    select_all_site_control_groups,
    upsert_many_doe,
)
from envoy.admin.mapper.site_control import SiteControlGroupListMapper, SiteControlListMapper
from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.doe import select_site_control_group_by_id
from envoy.server.manager.time import utc_now
from envoy.server.model.subscription import SubscriptionResource


class SiteControlGroupManager:

    @staticmethod
    async def create_site_control_group(session: AsyncSession, request: SiteControlGroupRequest) -> int:
        """Creates a new site control group"""
        now = utc_now()
        new_site_control_group = SiteControlGroupListMapper.map_from_request(request, now)

        session.add(new_site_control_group)
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE_CONTROL_GROUP, now)

        return new_site_control_group.site_control_group_id

    @staticmethod
    async def get_all_site_control_groups(
        session: AsyncSession, start: int, limit: int, changed_after: Optional[datetime]
    ) -> SiteControlGroupPageResponse:
        """Fetches a page of SiteControlGroup instances"""

        groups = await select_all_site_control_groups(session, start, limit, changed_after)
        group_count = await count_all_site_control_groups(session, changed_after)

        return SiteControlGroupListMapper.map_to_paged_response(
            total_count=group_count, limit=limit, start=start, after=changed_after, groups=groups
        )

    @staticmethod
    async def get_site_control_group_by_id(
        session: AsyncSession, site_control_group_id: int
    ) -> Optional[SiteControlGroupResponse]:
        """Selects a SiteControlGroupResponse for the specified ID or returns None if it does not exist"""
        scg = await select_site_control_group_by_id(session, site_control_group_id)
        if scg is None:
            return None

        return SiteControlGroupListMapper.map_to_response(scg)


class SiteControlListManager:
    @staticmethod
    async def delete_site_controls_in_range(
        session: AsyncSession,
        site_control_group_id: int,
        site_id: Optional[int],
        period_start: datetime,
        period_end: datetime,
    ) -> None:
        """deletes all site controls matching the specified parameters."""

        deleted_time = utc_now()
        await delete_does_with_start_time_in_range(
            session,
            site_control_group_id=site_control_group_id,
            site_id=site_id,
            period_start=period_start,
            period_end=period_end,
            deleted_time=deleted_time,
        )
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, deleted_time
        )
        return

    @staticmethod
    async def add_many_site_control(
        session: AsyncSession, site_control_group_id: int, control_list: list[SiteControlRequest]
    ) -> None:
        """Inserts many site controls into the db for the specified site_control_group."""

        changed_time = utc_now()
        doe_models = SiteControlListMapper.map_from_request(site_control_group_id, changed_time, control_list)
        await upsert_many_doe(session, doe_models, changed_time)
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, changed_time
        )

    @staticmethod
    async def get_all_site_controls(
        session: AsyncSession, site_control_group_id: int, start: int, limit: int, changed_after: Optional[datetime]
    ) -> SiteControlPageResponse:
        """Admin specific (paginated) fetch of site controls that covers all aggregators.
        changed_after: If specified - filter to does whose changed date is >= this value"""
        doe_count = await count_all_does(session, site_control_group_id, changed_after)
        does = await select_all_does(
            session,
            site_control_group_id=site_control_group_id,
            changed_after=changed_after,
            start=start,
            limit=limit,
        )
        return SiteControlListMapper.map_to_paged_response(
            total_count=doe_count,
            limit=limit,
            start=start,
            after=changed_after,
            does=does,
        )
