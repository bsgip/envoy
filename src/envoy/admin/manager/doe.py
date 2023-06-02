from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.doe import insert_single_doe, update_single_doe
from envoy.admin.mapper.doe import DoeMapper
from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdmin


class DoeManager:
    @staticmethod
    async def add_new_doe(session: AsyncSession, doe: DynamicOperatingEnvelopeAdmin) -> int:
        """TODO"""

        await insert_single_doe(session, DoeMapper.map_from_request(doe))
        await session.commit()
        return doe.dynamic_operating_envelope_id

    @staticmethod
    async def update_existing_doe(session: AsyncSession, doe: DynamicOperatingEnvelopeAdmin) -> int:
        """TODO"""

        await update_single_doe(session, DoeMapper.map_from_request(doe))
        await session.commit()
        return doe.dynamic_operating_envelope_id
