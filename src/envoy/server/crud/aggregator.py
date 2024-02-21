from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.aggregator import Aggregator


async def select_aggregator(
    session: AsyncSession,
    aggregator_id: int,
) -> Optional[Aggregator]:
    """Selects a specific Aggregator by ID. Will include Whitelisted Domains - returns None if it DNE"""

    stmt = select(Aggregator).where(Aggregator.aggregator_id == aggregator_id).options(selectinload(Aggregator.domains))

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()
