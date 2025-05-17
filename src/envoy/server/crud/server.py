from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.server import DynamicServerConfiguration


async def select_server_config(
    session: AsyncSession,
) -> Optional[DynamicServerConfiguration]:
    """Selects current server config"""

    stmt = select(DynamicServerConfiguration)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()
