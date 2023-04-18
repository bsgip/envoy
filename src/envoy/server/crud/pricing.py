from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional, Union

from sqlalchemy import Date, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site import Site
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


async def select_tariff_count(session: AsyncSession, after: datetime) -> int:
    """Fetches the number of tariffs stored

    after: Only tariffs with a changed_time greater than this value will be counted (set to 0 to count everything)"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = (
        select(func.count())
        .where((Tariff.changed_time >= after))
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_tariffs(
    session: AsyncSession,
    start: int,
    changed_after: datetime,
    limit: int,
) -> list[Tariff]:
    """Selects tariffs with some basic pagination / filtering based on change time

    Results will be ordered according to 2030.5 spec which is just on id DESC

    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = (
        select(Tariff)
        .where((Tariff.changed_time >= changed_after))
        .offset(start)
        .limit(limit)
        .order_by(
            Tariff.tariff_id.desc(),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_single_tariff(session: AsyncSession, tariff_id: int) -> Optional[Tariff]:
    """Requests a single tariff based on the primary key - returns None if it DNE"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = select(Tariff).where(
        (Tariff.tariff_id == tariff_id)
    )

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def _tariff_rates_for_day(is_counting: bool,
                                session: AsyncSession,
                                aggregator_id: int,
                                tariff_id: int,
                                site_id: int,
                                day: date,
                                start: int,
                                changed_after: datetime,
                                limit: Optional[int]) -> Union[list[TariffGeneratedRate], int]:
    """Internal utility for making _tariff_rates_for_day that either count or return the entities

    Orders by 2030.5 requirements on TimeTariffInterval which is start ASC, creation DESC, id DESC"""

    datetime_from = datetime.combine(day, time())
    datetime_to = datetime.combine(day + timedelta(days=1), time())

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = (
        select(TariffGeneratedRate.tariff_generated_rate_id if is_counting else TariffGeneratedRate)
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id) &
            (TariffGeneratedRate.start_time >= datetime_from) &
            (TariffGeneratedRate.start_time < datetime_to) &
            (TariffGeneratedRate.changed_time >= changed_after) &
            (TariffGeneratedRate.site_id == site_id) &
            (Site.aggregator_id == aggregator_id))
        .offset(start)
        .limit(limit)
        .order_by(
            TariffGeneratedRate.start_time.asc(),
            TariffGeneratedRate.changed_time.desc(),
            TariffGeneratedRate.tariff_generated_rate_id.desc())
    )

    if is_counting:
        stmt = select(func.count()).select_from(stmt)

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def count_tariff_rates_for_day(session: AsyncSession,
                                     aggregator_id: int,
                                     tariff_id: int,
                                     site_id: int,
                                     day: date,
                                     changed_after: datetime) -> int:
    """Fetches the number of TariffGeneratedRate's stored for the specified day

    changed_after: Only tariffs with a changed_time greater than this value will be counted (0 will count everything)"""

    return await _tariff_rates_for_day(True, session, aggregator_id, tariff_id, site_id, day, 0, changed_after, None)


async def select_tariff_rates_for_day(session: AsyncSession,
                                      aggregator_id: int,
                                      tariff_id: int,
                                      site_id: int,
                                      day: date,
                                      start: int,
                                      changed_after: datetime,
                                      limit: int) -> list[TariffGeneratedRate]:
    """Selects TariffGeneratedRate entities (with pagination) for a single tariff date

    tariff_id: The parent tariff primary key
    site_id: The specific site rates are being requested for
    day: The specific day of the year to restrict the lookup of values to
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on TimeTariffInterval which is start ASC, creation DESC, id DESC"""

    return await _tariff_rates_for_day(False, session, aggregator_id, tariff_id, site_id, day, start, changed_after,
                                       limit)


async def select_tariff_rate_for_day_time(session: AsyncSession,
                                          aggregator_id: int,
                                          tariff_id: int,
                                          site_id: int,
                                          day: date,
                                          time_of_day: time) -> Optional[TariffGeneratedRate]:
    """Selects single TariffGeneratedRate entity for a single tariff date / interval start

    time_of_day must be an EXACT match to return something (it's not enough to set it in the
    middle of an interval + duration)
    site_id: The specific site rates are being requested for
    tariff_id: The parent tariff primary key
    day: The specific day of the year to restrict the lookup of values to
    time_of_day: The specific time of day to find a match"""

    datetime_match = datetime.combine(day, time_of_day)

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = (
        select(TariffGeneratedRate)
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id) &
            (TariffGeneratedRate.start_time == datetime_match) &
            (TariffGeneratedRate.site_id == site_id) &
            (Site.aggregator_id == aggregator_id))
    )

    resp = await session.execute(stmt)
    return resp.scalars().one_or_none()


@dataclass
class TariffGeneratedRateStats:
    """Simple combo of some high level stats associated with TariffGenerateRate"""
    total_rates: int  # total number of TariffGeneratedRate
    first_rate: Optional[datetime]  # The lowest start_time for a TariffGeneratedRate (None if no rates)
    last_rate: Optional[datetime]  # The highest start_time for a TariffGeneratedRate (None if no rates)


@dataclass
class TariffGeneratedRateDailyStats:
    """Simple combo of some high level stats associated with TariffGenerateRate broken down by start_time.date"""
    total_distinct_dates: int  # total number of distinct dates (not just the specified page of data)
    single_date_counts: list[tuple[date, int]]  # each unique dates count of TariffGenerateRate instances. date ordered


async def select_rate_stats(session: AsyncSession,
                            aggregator_id: int,
                            tariff_id: int,
                            site_id: int,
                            changed_after: datetime) -> TariffGeneratedRateStats:
    """Calculates some basic statistics on TariffGeneratedRate

    tariff_id: The parent tariff primary key
    site_id: The specific site rates are being requested for
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)"""
    stmt = (
            select(func.count(), func.max(TariffGeneratedRate.start_time), func.min(TariffGeneratedRate.start_time))
            .join(TariffGeneratedRate.site)
            .where(
                (TariffGeneratedRate.tariff_id == tariff_id) &
                (TariffGeneratedRate.site_id == site_id) &
                (TariffGeneratedRate.changed_time >= changed_after) &
                (Site.aggregator_id == aggregator_id))
    )

    resp = await session.execute(stmt)
    (count, max_date, min_date) = resp.one()
    if count == 0:
        return TariffGeneratedRateStats(total_rates=count, first_rate=None, last_rate=None)
    else:
        return TariffGeneratedRateStats(total_rates=count, first_rate=min_date, last_rate=max_date)


async def select_rate_daily_stats(session: AsyncSession,
                                  aggregator_id: int,
                                  tariff_id: int,
                                  site_id: int,
                                  start: int,
                                  changed_after: datetime,
                                  limit: int) -> TariffGeneratedRateDailyStats:
    """Fetches the aggregate totals of TariffGeneratedRate grouped by the date upon which they occured.

    Results will be ordered by date ASC"""
    stmt_date_page = (
        select(cast(TariffGeneratedRate.start_time, Date).label("start_date"), func.count())
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id) &
            (TariffGeneratedRate.site_id == site_id) &
            (TariffGeneratedRate.changed_time >= changed_after) &
            (Site.aggregator_id == aggregator_id))
        .group_by("start_date")
        .order_by("start_date")
        .offset(start)
        .limit(limit)
    )
    resp = await session.execute(stmt_date_page)
    date_page = resp.fetchall()

    stmt_date_count = (
        select(func.count(distinct(cast(TariffGeneratedRate.start_time, Date))))
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id) &
            (TariffGeneratedRate.site_id == site_id) &
            (TariffGeneratedRate.changed_time >= changed_after) &
            (Site.aggregator_id == aggregator_id))
    )
    resp = await session.execute(stmt_date_count)
    count = resp.scalar_one()

    return TariffGeneratedRateDailyStats(total_distinct_dates=count, single_date_counts=date_page)