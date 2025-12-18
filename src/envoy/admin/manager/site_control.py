from datetime import datetime
from decimal import Decimal
from typing import Optional

from envoy_schema.admin.schema.site_control import (
    SiteControlGroupDefaultRequest,
    SiteControlGroupDefaultResponse,
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
    supersede_then_insert_does,
)
from envoy.admin.mapper.site_control import SiteControlGroupListMapper, SiteControlListMapper
from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.archive import copy_rows_into_archive
from envoy.server.crud.doe import select_site_control_group_by_id, select_site_control_group_fsa_ids
from envoy.server.manager.time import utc_now
from envoy.server.model.archive.doe import ArchiveSiteControlGroupDefault
from envoy.server.model.doe import SiteControlGroupDefault
from envoy.server.model.subscription import SubscriptionResource


class SiteControlGroupManager:

    @staticmethod
    async def create_site_control_group(session: AsyncSession, request: SiteControlGroupRequest) -> int:
        """Creates a new site control group"""
        now = utc_now()
        new_site_control_group = SiteControlGroupListMapper.map_from_request(request, now)

        existing_fsa_ids = await select_site_control_group_fsa_ids(session, datetime.min)
        is_new_fsa_id = new_site_control_group.fsa_id not in existing_fsa_ids

        session.add(new_site_control_group)
        await session.commit()

        if is_new_fsa_id:
            await NotificationManager.notify_changed_deleted_entities(
                SubscriptionResource.FUNCTION_SET_ASSIGNMENTS, now
            )
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

    @staticmethod
    async def update_site_control_default(
        session: AsyncSession, group_id: int, request: SiteControlGroupDefaultRequest
    ) -> bool:
        now = utc_now()

        scg = await select_site_control_group_by_id(session, group_id, include_default=True)
        if scg is None:
            return False

        if scg.site_control_group_default is None:
            scg.site_control_group_default = SiteControlGroupDefault(
                changed_time=now, version=0, site_control_group_id=group_id
            )
        else:
            # If there is an existing record - lets archive it BEFORE we update it
            await copy_rows_into_archive(
                session,
                SiteControlGroupDefault,
                ArchiveSiteControlGroupDefault,
                lambda q: q.where(SiteControlGroupDefault.site_control_group_id == group_id),
            )
            scg.site_control_group_default.changed_time = now

        if request.import_limit_watts is not None:
            scg.site_control_group_default.import_limit_active_watts = request.import_limit_watts.value

        if request.export_limit_watts is not None:
            scg.site_control_group_default.export_limit_active_watts = request.export_limit_watts.value

        if request.generation_limit_watts is not None:
            scg.site_control_group_default.generation_limit_active_watts = request.generation_limit_watts.value

        if request.load_limit_watts is not None:
            scg.site_control_group_default.load_limit_active_watts = request.load_limit_watts.value

        if request.ramp_rate_percent_per_second is not None:
            ramp_rate_value = (
                int(request.ramp_rate_percent_per_second.value)
                if request.ramp_rate_percent_per_second.value is not None
                else None
            )
            scg.site_control_group_default.ramp_rate_percent_per_second = ramp_rate_value

        scg.site_control_group_default.version = scg.site_control_group_default.version + 1

        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.DEFAULT_SITE_CONTROL, now)

        return True

    @staticmethod
    async def fetch_site_control_default_response(
        session: AsyncSession, group_id: int
    ) -> Optional[SiteControlGroupDefaultResponse]:
        """Fetches the current site control group default values as a SiteControlGroupDefaultResponse for external
        communication"""
        scg = await select_site_control_group_by_id(session, group_id, include_default=True)
        if not scg or not scg.site_control_group_default:
            return None

        return SiteControlGroupDefaultResponse(
            ramp_rate_percent_per_second=(
                Decimal(scg.site_control_group_default.ramp_rate_percent_per_second)
                if scg.site_control_group_default.ramp_rate_percent_per_second is not None
                else None
            ),
            server_default_import_limit_watts=scg.site_control_group_default.import_limit_active_watts,
            server_default_export_limit_watts=scg.site_control_group_default.export_limit_active_watts,
            server_default_generation_limit_watts=scg.site_control_group_default.generation_limit_active_watts,
            server_default_load_limit_watts=scg.site_control_group_default.load_limit_active_watts,
            changed_time=scg.site_control_group_default.changed_time,
            created_time=scg.site_control_group_default.created_time,
        )


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
        await supersede_then_insert_does(session, doe_models, changed_time)
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
