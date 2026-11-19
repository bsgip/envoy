from collections.abc import Iterable, Sequence
from typing import cast

import sqlalchemy as sa
from sqlalchemy import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.aggregator import (
    NULL_AGGREGATOR_ID,
    Aggregator,
    AggregatorCertificateAssignment,
    AggregatorDomain,
)


async def count_all_aggregators(session: AsyncSession) -> int:
    """Admin counting of aggregators - the NULL_AGGREGATOR (if present) will not be included"""
    stmt = sa.select(sa.func.count()).select_from(Aggregator).where(Aggregator.aggregator_id != NULL_AGGREGATOR_ID)
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_aggregators(session: AsyncSession, start: int | None, limit: int | None) -> Sequence[Aggregator]:
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


async def insert_single_aggregator(session: AsyncSession, aggregator: Aggregator) -> None:
    """Inserts a single aggregator entry into the DB. Returns None"""
    if aggregator.created_time:
        del aggregator.created_time
    session.add(aggregator)


async def update_single_aggregator(session: AsyncSession, updated_aggregator: Aggregator) -> None:
    """Updates a single existing aggregator entry in the DB."""

    resp = await session.execute(
        sa.select(Aggregator).where(Aggregator.aggregator_id == updated_aggregator.aggregator_id)
    )
    aggregator = resp.scalar_one()

    aggregator.changed_time = updated_aggregator.changed_time
    aggregator.name = updated_aggregator.name


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


async def count_aggregator_domains(session: AsyncSession, aggregator_id: int) -> int:
    """Counts the AggregatorDomains belonging to aggregator_id"""
    stmt = (
        sa.select(sa.func.count()).select_from(AggregatorDomain).where(AggregatorDomain.aggregator_id == aggregator_id)
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_aggregator_domains(
    session: AsyncSession, aggregator_id: int, start: int | None, limit: int | None
) -> Sequence[AggregatorDomain]:
    """Selects a page of AggregatorDomains belonging to aggregator_id, ordered by aggregator_domain_id"""
    stmt = (
        sa.select(AggregatorDomain)
        .where(AggregatorDomain.aggregator_id == aggregator_id)
        .order_by(AggregatorDomain.aggregator_domain_id.asc())
        .offset(start)
        .limit(limit)
    )
    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_aggregator_domain(session: AsyncSession, aggregator_domain_id: int) -> AggregatorDomain | None:
    """Selects a single AggregatorDomain by its ID. Domains belonging to the NULL_AGGREGATOR are never returned.
    Returns None if the domain can't be found."""
    stmt = sa.select(AggregatorDomain).where(
        (AggregatorDomain.aggregator_domain_id == aggregator_domain_id)
        & (AggregatorDomain.aggregator_id != NULL_AGGREGATOR_ID)
    )
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def insert_single_aggregator_domain(session: AsyncSession, aggregator_domain: AggregatorDomain) -> None:
    """Inserts a single AggregatorDomain into the DB (aggregator_domain will be populated with the new ID on flush)"""
    if aggregator_domain.created_time:
        del aggregator_domain.created_time
    session.add(aggregator_domain)
    await session.flush()


async def delete_single_aggregator_domain(session: AsyncSession, aggregator_domain_id: int) -> bool:
    """Deletes a single AggregatorDomain by ID (domains of the NULL_AGGREGATOR will NOT be deleted).
    Returns True if a domain was deleted, False otherwise"""
    resp = await session.execute(
        sa.delete(AggregatorDomain).where(
            (AggregatorDomain.aggregator_domain_id == aggregator_domain_id)
            & (AggregatorDomain.aggregator_id != NULL_AGGREGATOR_ID)
        )
    )
    return cast(CursorResult, resp).rowcount > 0
