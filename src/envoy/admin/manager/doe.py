from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.doe import upsert_many_doe
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
        await upsert_many_doe(session, doe_models)
        await session.commit()

        await NotificationManager.notify_upserted_entities(
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, changed_time
        )
