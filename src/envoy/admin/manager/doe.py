from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.doe import insert_single_doe, select_single_doe, update_single_doe
from envoy.admin.mapper.doe import DoeMapper
from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdminRequest, DynamicOperatingEnvelopeAdminResponse


class DoeManager:
    @staticmethod
    async def add_new_doe(session: AsyncSession, doe: DynamicOperatingEnvelopeAdminRequest) -> int:
        """Insert a single DOE into the db. Returns the ID of the inserted DOE."""

        doe_model = DoeMapper.map_from_request(doe)
        await insert_single_doe(session, doe_model)
        await session.commit()
        return doe_model.dynamic_operating_envelope_id

    @staticmethod
    async def update_existing_doe(session: AsyncSession, doe: DynamicOperatingEnvelopeAdminRequest) -> int:
        """Update an existing DOE from the db. Returns the ID of the modified DOE."""

        doe_model = DoeMapper.map_from_request(doe)
        await update_single_doe(session, doe_model)
        await session.commit()
        return doe_model.dynamic_operating_envelope_id

    @staticmethod
    async def fetch_doe(session: AsyncSession, doe_id: int) -> DynamicOperatingEnvelopeAdminResponse:
        """Select a single DOE from the db and map to the appropriate response"""

        doe = await select_single_doe(session, doe_id)
        if doe is None:
            raise NoResultFound
        return DoeMapper.map_to_response(doe)
