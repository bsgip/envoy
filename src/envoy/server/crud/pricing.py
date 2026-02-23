from datetime import date, datetime, time, timedelta
from itertools import islice
from typing import Optional, Sequence, Union

from sqlalchemy import TIMESTAMP, Date, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.common import localize_start_time, localize_start_time_for_entity
from envoy.server.model.site import Site
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate


async def select_tariff_fsa_ids(session: AsyncSession, changed_after: datetime) -> Sequence[int]:
    """Fetches the distinct values for "fsa_id" across all Tariff instances (optionally filtering
    on Tariff.changed_time that were changed after changed_after)"""
    stmt = select(func.distinct(Tariff.fsa_id))
    if changed_after != datetime.min:
        stmt = stmt.where(Tariff.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_tariff_count(session: AsyncSession, after: datetime, fsa_id: Optional[int]) -> int:
    """Fetches the number of tariffs stored

    after: Only tariffs with a changed_time greater than this value will be counted (set to 0 to count everything)
    fsa_id: If specified - only count Tariffs with this value for fsa_id"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = select(func.count()).select_from(Tariff)

    if after != datetime.min:
        stmt = stmt.where((Tariff.changed_time >= after))

    if fsa_id is not None:
        stmt = stmt.where((Tariff.fsa_id == fsa_id))

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_tariffs(
    session: AsyncSession, start: int, changed_after: datetime, limit: int, fsa_id: Optional[int]
) -> Sequence[Tariff]:
    """Selects tariffs with some basic pagination / filtering based on change time

    Results will be ordered according to sep2 spec which is just on id DESC

    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)
    fsa_id: If specified - only include Tariffs with this value for fsa_id"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = (
        select(Tariff)
        .offset(start)
        .limit(limit)
        .order_by(
            Tariff.tariff_id.desc(),
        )
    )

    if changed_after != datetime.min:
        stmt = stmt.where((Tariff.changed_time >= changed_after))

    if fsa_id is not None:
        stmt = stmt.where((Tariff.fsa_id == fsa_id))

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_single_tariff(session: AsyncSession, tariff_id: int) -> Optional[Tariff]:
    """Requests a single tariff based on the primary key - returns None if it does not exist"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = select(Tariff).where((Tariff.tariff_id == tariff_id))

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_tariff_generated_rate_for_scope(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    rate_id: int,
) -> Optional[TariffGeneratedRate]:
    """Attempts to fetch a TariffGeneratedRate using its primary id, also scoping it to a particular aggregator/site

    aggregator_id: The aggregator id to constrain the lookup to
    site_id: If None - no effect otherwise the query will apply a filter on site_id using this value"""

    stmt = (
        select(TariffGeneratedRate, Site.timezone_id)
        .join(TariffGeneratedRate.site)
        .where((TariffGeneratedRate.tariff_generated_rate_id == rate_id) & (Site.aggregator_id == aggregator_id))
    )
    if site_id is not None:
        stmt = stmt.where(TariffGeneratedRate.site_id == site_id)

    resp = await session.execute(stmt)
    raw = resp.one_or_none()
    if raw is None:
        return None
    return localize_start_time(raw)


async def select_tariff_component_by_id(
    session: AsyncSession,
    tariff_component_id: int,
) -> Optional[TariffComponent]:
    """Attempts to fetch a TariffComponent using its primary id"""

    stmt = select(TariffComponent).where((TariffComponent.tariff_component_id == tariff_component_id))
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_tariff_components_by_tariff(
    session: AsyncSession,
    tariff_id: int,
    start: int,
    changed_after: Optional[datetime],
    limit: int,
) -> Sequence[TariffComponent]:
    """Attempts to fetch all TariffComponents underneath a Tariff. Will order according to 2030.5 requirements.
    Supports basic pagination.

    changed_after: Only fetch records created/modified on/after this time"""

    stmt = (
        select(TariffComponent)
        .where((TariffComponent.tariff_id == tariff_id))
        .order_by(TariffComponent.tariff_component_id.desc())  # Ordered by 2030.5 RateComponent ordering
        .limit(limit)
        .offset(start)
    )
    if changed_after is not None:
        stmt = stmt.where(TariffComponent.changed_time >= changed_after)
    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_tariff_components_by_tariff(
    session: AsyncSession,
    tariff_id: int,
    changed_after: Optional[datetime],
) -> int:
    """Attempts to count all TariffComponents underneath a Tariff.

    changed_after: Only count records created/modified on/after this time"""

    stmt = select(func.count()).select_from(TariffComponent).where((TariffComponent.tariff_id == tariff_id))
    if changed_after is not None:
        stmt = stmt.where(TariffComponent.changed_time >= changed_after)
    resp = await session.execute(stmt)
    return resp.scalar_one()
