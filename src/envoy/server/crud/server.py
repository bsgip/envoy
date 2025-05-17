from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.server import RuntimeServerConfig


async def select_server_config(
    session: AsyncSession,
) -> Optional[RuntimeServerConfig]:
    """Returns the only row in the server configuration table (id = 1), if it exists."""

    stmt = select(RuntimeServerConfig).where(RuntimeServerConfig.runtime_server_config_id == 1)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()
