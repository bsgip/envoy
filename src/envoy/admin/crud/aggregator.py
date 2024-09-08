from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.aggregator import NULL_AGGREGATOR_ID, Aggregator


async def count_all_aggregators(session: AsyncSession) -> int:
    """Admin counting of aggregators - the NULL_AGGREGATOR (if present) will not be included"""
    stmt = select(func.count()).select_from(Aggregator).where(Aggregator.aggregator_id != NULL_AGGREGATOR_ID)
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_aggregators(session: AsyncSession, start: int, limit: int) -> Sequence[Aggregator]:
    """Admin selecting of aggregators - will include domains relationship (the NULL_AGGREGATOR is not included)"""

    stmt = (
        select(Aggregator)
        .offset(start)
        .limit(limit)
        .where(Aggregator.aggregator_id != NULL_AGGREGATOR_ID)
        .order_by(
            Aggregator.aggregator_id.asc(),
        )
        .options(
            selectinload(Aggregator.domains),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()
