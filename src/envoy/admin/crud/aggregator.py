from typing import Sequence, Iterable

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.aggregator import NULL_AGGREGATOR_ID, Aggregator, AggregatorCertificateAssignment


async def count_all_aggregators(session: AsyncSession) -> int:
    """Admin counting of aggregators - the NULL_AGGREGATOR (if present) will not be included"""
    stmt = sa.select(sa.func.count()).select_from(Aggregator).where(Aggregator.aggregator_id != NULL_AGGREGATOR_ID)
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_aggregators(session: AsyncSession, start: int, limit: int) -> Sequence[Aggregator]:
    """Admin selecting of aggregators - will include domains relationship (the NULL_AGGREGATOR is not included)"""

    stmt = (
        sa.select(Aggregator)
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


async def assign_many_certificates(session: AsyncSession, aggregator_id: int, certificate_ids: Iterable[int]) -> None:
    """Assigns certificates to an aggregator.

    Certificates are expected to exist prior to assignment.

    Args:
        session: Database session
        aggregator_id: ID of aggregator to have certificates assigned
        certficate_ids: IDs of existing certificates to be assigned
    """
    new_relations = [{"aggregator_id": aggregator_id, "certificate_id": cid} for cid in certificate_ids]
    stmt = sa.insert(AggregatorCertificateAssignment).values(new_relations)
    await session.execute(stmt)


async def unassign_many_certificates(session: AsyncSession, aggregator_id: int, certificate_ids: Iterable[int]) -> None:
    """Unassign certificates from an aggregator.

    Does nothing if the relationship doesn't exist.

    Args:
        session: Database session
        aggregator_id: ID of aggregator to have certificates unasssigned
        certificate_ids: IDs of all certificates to unassign
    """
    stmt = (
        sa.delete(AggregatorCertificateAssignment)
        .where(AggregatorCertificateAssignment.aggregator_id == aggregator_id)
        .where(AggregatorCertificateAssignment.certificate_id.in_(certificate_ids))
    )
    await session.execute(stmt)
