from datetime import date, datetime, time, timedelta
from itertools import islice
from typing import Optional, Sequence, Union

from sqlalchemy import TIMESTAMP, Date, Select, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.common import localize_start_time, localize_start_time_for_entity
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
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


async def count_active_rates_include_deleted(
    session: AsyncSession,
    tariff_id: int,
    tariff_component_id: Optional[int],
    site: Site,
    now: datetime,
    changed_after: datetime,
) -> int:
    """Provides the count of records returned from select_active_rates_include_deleted (assuming no pagination).

    tariff_id: The parent TariffID to filter results to (only used if tariff_component_id is None)
    tariff_component_id: If specified - ONLY filter for results underneath this ID (tariff_id is NOT considered)
    site: The site that the counted rates will be all be scoped from
    now: The timestamp that excludes any rate whose end_time precedes this (they are expired and no longer relevant)
    changed_after: Only rates modified after this time will be counted."""

    count_active_rates_stmt = (
        select(func.count())
        .select_from(TariffGeneratedRate)
        .where((TariffGeneratedRate.end_time > now) & (TariffGeneratedRate.site_id == site.site_id))
    )
    if tariff_component_id is None:
        count_active_rates_stmt = count_active_rates_stmt.where(TariffGeneratedRate.tariff_id == tariff_id)
    else:
        count_active_rates_stmt = count_active_rates_stmt.where(
            TariffGeneratedRate.tariff_component_id == tariff_component_id
        )

    count_archive_rates_stmt = (
        select(func.count())
        .select_from(ArchiveTariffGeneratedRate)
        .where(
            (ArchiveTariffGeneratedRate.end_time > now)
            & (ArchiveTariffGeneratedRate.site_id == site.site_id)
            & (ArchiveTariffGeneratedRate.deleted_time.is_not(None))
        )
    )
    if tariff_component_id is None:
        count_archive_rates_stmt = count_archive_rates_stmt.where(ArchiveTariffGeneratedRate.tariff_id == tariff_id)
    else:
        count_archive_rates_stmt = count_archive_rates_stmt.where(
            ArchiveTariffGeneratedRate.tariff_component_id == tariff_component_id
        )

    if changed_after != datetime.min:
        # The "changed_time" for archives is actually the "deleted_time"
        count_active_rates_stmt = count_active_rates_stmt.where(TariffGeneratedRate.changed_time >= changed_after)
        count_archive_rates_stmt = count_archive_rates_stmt.where(
            ArchiveTariffGeneratedRate.deleted_time >= changed_after
        )

    count_active = (await session.execute(count_active_rates_stmt)).scalar_one()
    count_archive = (await session.execute(count_archive_rates_stmt)).scalar_one()

    return count_active + count_archive


async def select_active_rates_include_deleted(
    session: AsyncSession,
    tariff_id: int,
    tariff_component_id: Optional[int],
    site: Site,
    now: datetime,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> list[Union[TariffGeneratedRate, ArchiveTariffGeneratedRate]]:
    """Fetches TariffGeneratedRate from its primary table AND archive according to the specified filter criteria. Only
    TariffGeneratedRate's whose end_time is after "now" will be returned.

    tariff_id: The parent TariffID to filter results to (only used if tariff_component_id is None)
    tariff_component_id: If specified - ONLY filter for results underneath this ID (tariff_id is NOT considered)
    site: Only TariffGeneratedRate from this site will be included
    now: The timestamp that excludes any TariffGeneratedRate whose end_time precedes this (i.e. they are expired and no
         longer relevant)
    start: How many TariffGeneratedRate to skip
    limit: Max number of TariffGeneratedRate to return
    changed_after: Only TariffGeneratedRate's modified after this time will be included.

    Orders by 2030.5 requirements on TimeTariffInterval which is start ASC, creation DESC, id DESC"""

    select_active_rates = select(
        TariffGeneratedRate.tariff_generated_rate_id,
        TariffGeneratedRate.tariff_id,
        TariffGeneratedRate.tariff_component_id,
        TariffGeneratedRate.site_id,
        TariffGeneratedRate.calculation_log_id,
        TariffGeneratedRate.start_time,
        TariffGeneratedRate.duration_seconds,
        TariffGeneratedRate.end_time,
        TariffGeneratedRate.price_pow10_encoded,
        TariffGeneratedRate.created_time,
        TariffGeneratedRate.changed_time,
        literal_column("NULL").label("archive_id"),
        literal_column("NULL").label("archive_time"),
        literal_column("NULL").label("deleted_time"),
        literal_column("0").label("is_archive"),
    ).where((TariffGeneratedRate.end_time > now) & (TariffGeneratedRate.site_id == site.site_id))
    if tariff_component_id is None:
        select_active_rates = select_active_rates.where(TariffGeneratedRate.tariff_id == tariff_id)
    else:
        select_active_rates = select_active_rates.where(TariffGeneratedRate.tariff_component_id == tariff_component_id)

    select_archive_rates = select(
        ArchiveTariffGeneratedRate.tariff_generated_rate_id,
        ArchiveTariffGeneratedRate.tariff_id,
        ArchiveTariffGeneratedRate.tariff_component_id,
        ArchiveTariffGeneratedRate.site_id,
        ArchiveTariffGeneratedRate.calculation_log_id,
        ArchiveTariffGeneratedRate.start_time,
        ArchiveTariffGeneratedRate.duration_seconds,
        ArchiveTariffGeneratedRate.end_time,
        ArchiveTariffGeneratedRate.price_pow10_encoded,
        ArchiveTariffGeneratedRate.created_time,
        ArchiveTariffGeneratedRate.changed_time,
        ArchiveTariffGeneratedRate.archive_id,
        ArchiveTariffGeneratedRate.archive_time,
        ArchiveTariffGeneratedRate.deleted_time,
        literal_column("1").label("is_archive"),
    ).where(
        (ArchiveTariffGeneratedRate.end_time > now)
        & (ArchiveTariffGeneratedRate.site_id == site.site_id)
        & (ArchiveTariffGeneratedRate.deleted_time.is_not(None))
    )
    if tariff_component_id is None:
        select_archive_rates = select_archive_rates.where(ArchiveTariffGeneratedRate.tariff_id == tariff_id)
    else:
        select_archive_rates = select_archive_rates.where(
            ArchiveTariffGeneratedRate.tariff_component_id == tariff_component_id
        )

    if changed_after != datetime.min:
        # The "changed_time" for archives is actually the "deleted_time"
        select_active_rates = select_active_rates.where(TariffGeneratedRate.changed_time >= changed_after)
        select_archive_rates = select_archive_rates.where(ArchiveTariffGeneratedRate.deleted_time >= changed_after)

    stmt = (
        select_active_rates.union_all(select_archive_rates)
        .limit(limit)
        .offset(start)
        .order_by(
            TariffGeneratedRate.start_time.asc(),
            TariffGeneratedRate.changed_time.desc(),
            TariffGeneratedRate.tariff_generated_rate_id.desc(),
        )
    )

    resp = await session.execute(stmt)

    # This is (annoyingly) the only real way to take the UNION ALL query and return multiple element types
    # We use the literal "is_archive" from our query to differentiate archive from normal rows
    return [
        (
            localize_start_time_for_entity(
                ArchiveTariffGeneratedRate(
                    tariff_generated_rate_id=t.tariff_generated_rate_id,
                    tariff_id=t.tariff_id,
                    tariff_component_id=t.tariff_component_id,
                    site_id=t.site_id,
                    calculation_log_id=t.calculation_log_id,
                    start_time=t.start_time,
                    duration_seconds=t.duration_seconds,
                    end_time=t.end_time,
                    price_pow10_encoded=t.price_pow10_encoded,
                    created_time=t.created_time,
                    changed_time=t.changed_time,
                    archive_id=t.archive_id,
                    archive_time=t.archive_time,
                    deleted_time=t.deleted_time,
                ),
                site.timezone_id,
            )
            if t.is_archive
            else localize_start_time_for_entity(
                TariffGeneratedRate(
                    tariff_generated_rate_id=t.tariff_generated_rate_id,
                    tariff_id=t.tariff_id,
                    tariff_component_id=t.tariff_component_id,
                    site_id=t.site_id,
                    calculation_log_id=t.calculation_log_id,
                    start_time=t.start_time,
                    duration_seconds=t.duration_seconds,
                    end_time=t.end_time,
                    price_pow10_encoded=t.price_pow10_encoded,
                    created_time=t.created_time,
                    changed_time=t.changed_time,
                ),
                site.timezone_id,
            )
        )
        for t in resp.all()
    ]
