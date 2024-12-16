from datetime import datetime
from typing import Optional

from envoy_schema.admin.schema.doe import DoePageResponse, DynamicOperatingEnvelopeRequest
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.doe import count_all_does, select_all_does, upsert_many_doe
from envoy.admin.mapper.doe import DoeListMapper
from envoy.notification.manager.notification import NotificationManager
from envoy.server.manager.time import utc_now
from envoy.server.model.subscription import SubscriptionResource


class DoeListManager:
    @staticmethod
    async def add_many_doe(session: AsyncSession, doe_list: list[DynamicOperatingEnvelopeRequest]) -> None:
        """Insert a single DOE into the db. Returns the ID of the inserted DOE."""

        changed_time = utc_now()
        doe_models = DoeListMapper.map_from_request(changed_time, doe_list)
        await upsert_many_doe(session, doe_models, changed_time)
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, changed_time
        )

    @staticmethod
    async def get_all_does(
        session: AsyncSession, start: int, limit: int, changed_after: Optional[datetime]
    ) -> DoePageResponse:
        """Admin specific (paginated) fetch of does that covers all aggregators.
        changed_after: If specified - filter to does whose changed date is >= this value"""
        doe_count = await count_all_does(session, changed_after)
        does = await select_all_does(
            session,
            changed_after=changed_after,
            start=start,
            limit=limit,
        )
        return DoeListMapper.map_to_paged_response(
            total_count=doe_count,
            limit=limit,
            start=start,
            after=changed_after,
            does=does,
        )
