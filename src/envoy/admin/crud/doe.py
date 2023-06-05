from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.doe import DynamicOperatingEnvelope


async def insert_single_doe(session: AsyncSession, doe: DynamicOperatingEnvelope) -> None:
    """Adds a single DynamicOperatingEnvelope into the db. Returns None."""
    session.add(doe)


async def update_single_doe(session: AsyncSession, updated_doe: DynamicOperatingEnvelope) -> None:
    """Updates an existing DOE in the db, if a matching one exists."""

    resp = await session.execute(
        select(DynamicOperatingEnvelope).filter_by(
            dynamic_operating_envelope_id=updated_doe.dynamic_operating_envelope_id
        )
    )

    # TODO this will raise an exception if not found?
    doe = resp.scalar_one()

    doe.changed_time = updated_doe.changed_time
    doe.site_id = updated_doe.site_id
    doe.start_time = updated_doe.start_time
    doe.duration_seconds = updated_doe.duration_seconds
    doe.import_limit_active_watts = updated_doe.import_limit_active_watts
    doe.export_limit_watts = updated_doe.export_limit_watts


async def select_single_doe(session: AsyncSession, doe_id: int) -> DynamicOperatingEnvelope:
    """Selects a single DOE from a matching doe_id"""

    resp = await session.execute(select(DynamicOperatingEnvelope).filter_by(dynamic_operating_envelope_id=doe_id))
    return resp.scalar_one()
