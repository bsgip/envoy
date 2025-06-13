from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model import aggregator
from envoy.server.model import base


async def count_certificates_for_aggregator(session: AsyncSession, aggregator_id: int) -> int:
    """Admin counting of certificates for a given aggregator"""
    stmt = (
        select(func.count())
        .select_from(aggregator.AggregatorCertificateAssignment)
        .where(aggregator.AggregatorCertificateAssignment.aggregator_id == aggregator_id)
    )

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_certificates_for_aggregator(
    session: AsyncSession, aggregator_id: int, start: int, limit: int
) -> Sequence[base.Certificate]:
    """Selects all certificates for a given aggregator

    Args:
        session: Database session
        aggregator_id: ID to use for limiting results
        start: Count of results to skip
        limit: Count of results to return

    Returns:
        A collection of Certificates
    """
    stmt = (
        select(base.Certificate)
        .offset(start)
        .limit(limit)
        .join(aggregator.AggregatorCertificateAssignment)
        .where(aggregator.AggregatorCertificateAssignment.aggregator_id == aggregator_id)
        .order_by(base.Certificate.certificate_id.asc())
    )
    resp = await session.execute(stmt)

    return resp.scalars().all()
