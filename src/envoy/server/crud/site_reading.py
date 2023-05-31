from datetime import datetime
from typing import Iterable, Optional, Sequence, Union

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType


async def fetch_site_reading_type_for_aggregator(
    session: AsyncSession, aggregator_id: int, site_reading_type_id: int, include_site_relation: bool
) -> Optional[SiteReadingType]:
    """Fetches the SiteReadingType by ID (also validating aggregator_id) - returns None if it can't be found

    if include_site_relation is True - the site relation will also be populated (defaults to raise otherwise)
    """
    stmt = select(SiteReadingType).where(
        (SiteReadingType.site_reading_type_id == site_reading_type_id)
        & (SiteReadingType.aggregator_id == aggregator_id)
    )

    if include_site_relation:
        stmt = stmt.options(selectinload(SiteReadingType.site))

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def _site_reading_types_for_aggregator(
    only_count: bool,
    session: AsyncSession,
    aggregator_id: int,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[SiteReadingType], int]:
    """Internal utility for making site_reading_types_for_aggregator  requests that either counts the entities or
    returns a page of the entities

    Orders by sep2 requirements on MirrorUsagePoint which is id DESC"""

    select_clause: Union[Select[tuple[int]], Select[tuple[SiteReadingType]]]
    if only_count:
        select_clause = select(func.count()).select_from(SiteReadingType)
    else:
        select_clause = select(SiteReadingType)

    stmt = (
        select_clause.join(Site)
        .where(
            (SiteReadingType.aggregator_id == aggregator_id)
            & (SiteReadingType.changed_time >= changed_after)
            & (Site.aggregator_id == aggregator_id)  # Only fetch sites that are currently assigned to this aggregator
        )
        .offset(start)
        .limit(limit)
    )

    if not only_count:
        stmt = stmt.options(selectinload(SiteReadingType.site)).order_by(
            SiteReadingType.site_reading_type_id.desc(),
        )

    resp = await session.execute(stmt)
    if only_count:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def fetch_site_reading_types_page_for_aggregator(
    session: AsyncSession,
    aggregator_id: int,
    start: int,
    limit: int,
    changed_after: datetime,
) -> Sequence[SiteReadingType]:
    """Fetches a page of SiteReadingType for a particular aggregator_id. The SiteReadingType will have the
    reference Site included"""
    return await _site_reading_types_for_aggregator(
        False, session, aggregator_id=aggregator_id, start=start, limit=limit, changed_after=changed_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def count_site_reading_types_for_aggregator(
    session: AsyncSession,
    aggregator_id: int,
    changed_after: datetime,
) -> int:
    """Fetches a page of SiteReadingType for a particular aggregator_id"""
    return await _site_reading_types_for_aggregator(
        True, session, aggregator_id=aggregator_id, start=0, limit=None, changed_after=changed_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def upsert_site_reading_type_for_aggregator(
    session: AsyncSession, aggregator_id: int, site_reading_type: SiteReadingType
) -> int:
    """Creates or updates the specified site reading type. If site's aggregator_id doesn't match aggregator_id then
    this will raise an error without modifying the DB. Returns the site_reading_type_id of the inserted/existing site

    Relying on postgresql dialect for upsert capability. Unfortunately this breaks the typical ORM insert pattern.

    Returns the site_reading_type_id of the created/updated SiteReadingType"""

    if aggregator_id != site_reading_type.aggregator_id:
        raise ValueError(
            f"Specified aggregator_id {aggregator_id} mismatches site.aggregator_id {site_reading_type.aggregator_id}"
        )

    table = SiteReadingType.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns)]  # type: ignore [attr-defined]
    stmt = psql_insert(SiteReadingType).values(**{k: getattr(site_reading_type, k) for k in update_cols})
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            SiteReadingType.aggregator_id,
            SiteReadingType.site_id,
            SiteReadingType.uom,
            SiteReadingType.data_qualifier,
            SiteReadingType.flow_direction,
            SiteReadingType.accumulation_behaviour,
            SiteReadingType.kind,
            SiteReadingType.phase,
            SiteReadingType.power_of_ten_multiplier,
            SiteReadingType.default_interval_seconds,
        ],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    ).returning(SiteReadingType.site_reading_type_id)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def upsert_site_readings(session: AsyncSession, site_readings: Iterable[SiteReading]):
    """Creates or updates the specified site readings. It's assumed that each SiteReading will have
    been assigned a valid site_reading_type_id before calling this function. No validation will be made for ownership

    Relying on postgresql dialect for upsert capability. Unfortunately this breaks the typical ORM insert pattern."""

    table = SiteReading.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns)]  # type: ignore [attr-defined]
    stmt = psql_insert(SiteReading).values([{k: getattr(sr, k) for k in update_cols} for sr in site_readings])
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            SiteReading.site_reading_type_id,
            SiteReading.time_period_start,
        ],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    )

    await session.execute(stmt)
