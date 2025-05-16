from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.server import RuntimeServerConfig


async def select_server_config(
    session: AsyncSession,
) -> Optional[RuntimeServerConfig]:
    """Selects current server config"""

    stmt = select(RuntimeServerConfig)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()
