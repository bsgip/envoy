from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.doe import DynamicOperatingEnvelope


async def insert_single_doe(session: AsyncSession, doe: DynamicOperatingEnvelope) -> None:
    session.add(doe)


async def update_single_doe(session: AsyncSession, updated_doe: DynamicOperatingEnvelope) -> None:
    resp = await session.execute(
        select(DynamicOperatingEnvelope).filter_by(
            dynamic_operating_envelope_id=updated_doe.dynamic_operating_envelope_id
        )
    )
    doe = resp.scalar_one()

    doe.changed_time = updated_doe.changed_time
    doe.start_time = updated_doe.start_time
    doe.duration_seconds = updated_doe.duration_seconds
    doe.import_limit_active_watts = updated_doe.import_limit_active_watts
    doe.export_limit_watts = updated_doe.export_limit_watts

    # site id?
    # site?
