from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.doe import upsert_many_doe
from envoy.admin.mapper.doe import DoeListMapper


class DoeListManager:
    @staticmethod
    async def add_many_doe(session: AsyncSession, doe_list: list[DynamicOperatingEnvelopeRequest]) -> None:
        """Insert a single DOE into the db. Returns the ID of the inserted DOE."""

        doe_models = DoeListMapper.map_from_request(doe_list)
        await upsert_many_doe(session, doe_models)
        await session.commit()
