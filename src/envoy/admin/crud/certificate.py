from typing import Sequence, Iterable

import itertools

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects import postgresql

from envoy.server.model import aggregator
from envoy.server.model import base


async def count_certificates_for_aggregator(session: AsyncSession, aggregator_id: int) -> int:
    """Admin counting of certificates for a given aggregator"""
    stmt = (
        sa.select(sa.func.count())
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
        sa.select(base.Certificate)
        .offset(start)
        .limit(limit)
        .join(aggregator.AggregatorCertificateAssignment)
        .where(aggregator.AggregatorCertificateAssignment.aggregator_id == aggregator_id)
        .order_by(base.Certificate.certificate_id.asc())
    )
    resp = await session.execute(stmt)

    return resp.scalars().all()


async def select_all_certificates(session: AsyncSession, start: int, limit: int) -> Sequence[base.Certificate]:
    """Retrieve all certificates from db, sorted by certificate_id

    Args:
        session: Database session
        start: Count of results to skip
        limit: Count of results to return

    Returns:
        A collection of Certificates
    """
    stmt = sa.select(base.Certificate).offset(start).limit(limit).order_by(base.Certificate.certificate_id.asc())
    resp = await session.execute(stmt)

    return resp.scalars().all()


async def select_many_certificates_by_id_or_lfdi(
    session: AsyncSession, certificates: list[base.Certificate]
) -> Sequence[base.Certificate]:
    """Selects all certificates available using either ID or LFDI.

    Args:
        session: Database session
        certificates: All certificates being checked for existance in DB.
            This may be a superset of those returned

    Returns:
        A collection of Certificates
    """
    certificate_ids = (c.certificate_id for c in certificates if c.certificate_id is not None)
    lfdis = (c.lfdi for c in certificates if c.lfdi is not None)
    stmt = sa.select(base.Certificate).where(
        sa.or_(base.Certificate.certificate_id.in_(certificate_ids), base.Certificate.lfdi.in_(lfdis))
    )
    resp = await session.execute(stmt)

    return resp.scalars().all()


async def create_many_certificates(session: AsyncSession, certificates: list[base.Certificate]) -> None:
    """Creates certificates for all those provided.

    Does not upsert. All certificates are expected to not exist.

    Args:
        session: Database session
        certificates: All certificates to be created
    """
    table = base.Certificate.__table__
    create_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    stmt = sa.insert(base.Certificate).values(([{k: getattr(cert, k) for k in create_cols} for cert in certificates]))
    await session.execute(stmt)


async def create_many_certificates_on_conflict_do_nothing(
    session: AsyncSession, certificates: Iterable[base.Certificate]
) -> Sequence[base.Certificate]:
    """Attempts to create certificates for all those provided.

    Fails quietly if conflict occurs i.e. duplicate LFDI present. Does not upsert.
    The query is specific to PostgreSQL databases.

    Args:
        session: Database session
        certificates: All certificates potentially to be created

    Returns:
        All certificates that were created
    """
    # Determine if an empty iterable was provided, if so return empty list
    peeker, producer = itertools.tee(iter(certificates))
    try:
        next(peeker)
    except StopIteration:
        return []

    table = base.Certificate.__table__
    create_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    stmt = (
        postgresql.insert(base.Certificate)
        .values(([{k: getattr(cert, k) for k in create_cols} for cert in producer]))
        .on_conflict_do_nothing(index_elements=["lfdi"])
        .returning(base.Certificate)
    )
    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_certificate(session: AsyncSession, certificate_id: int) -> base.Certificate | None:
    """Select a single certificate by ID"""
    stmt = sa.select(base.Certificate).where(base.Certificate.certificate_id == certificate_id)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()
