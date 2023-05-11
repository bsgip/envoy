from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional, Sequence, Union
from zoneinfo import ZoneInfo

from sqlalchemy import TIMESTAMP, Date, Row, Select, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site import Site
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


def _localize_start_time(rate_and_tz: Optional[Row[tuple[TariffGeneratedRate, str]]]) -> TariffGeneratedRate:
    """Localizes a TariffGeneratedRate.start_time to be in the local timezone passed in as the second
    element in the tuple. Returns the TariffGeneratedRate (it will be modified in place)"""
    if rate_and_tz is None:
        raise ValueError("row is None")

    (rate, tz_name) = rate_and_tz
    tz = ZoneInfo(tz_name)
    rate.start_time = rate.start_time.astimezone(tz)
    return rate


async def select_tariff_count(session: AsyncSession, after: datetime) -> int:
    """Fetches the number of tariffs stored

    after: Only tariffs with a changed_time greater than this value will be counted (set to 0 to count everything)"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = select(func.count()).where((Tariff.changed_time >= after))
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_tariffs(
    session: AsyncSession,
    start: int,
    changed_after: datetime,
    limit: int,
) -> Sequence[Tariff]:
    """Selects tariffs with some basic pagination / filtering based on change time

    Results will be ordered according to sep2 spec which is just on id DESC

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
    """Requests a single tariff based on the primary key - returns None if it does not exist"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    stmt = select(Tariff).where((Tariff.tariff_id == tariff_id))

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def _tariff_rates_for_day(
    only_count: bool,
    session: AsyncSession,
    aggregator_id: int,
    tariff_id: int,
    site_id: int,
    day: date,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[TariffGeneratedRate], int]:
    """Internal utility for making _tariff_rates_for_day that either counts the entities or returns the entities

    Orders by sep2 requirements on TimeTariffInterval which is start ASC, creation DESC, id DESC"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    select_clause: Union[Select[tuple[int]], Select[tuple[TariffGeneratedRate, str]]]
    if only_count:
        select_clause = select(func.count()).select_from(TariffGeneratedRate)
    else:
        select_clause = select(TariffGeneratedRate, Site.timezone_id)

    # To best utilise the rate indexes - we map our literal start/end times to the site local time zone
    tz_adjusted_from_expr = func.timezone(Site.timezone_id, cast(day, TIMESTAMP))
    tz_adjusted_to_expr = func.timezone(Site.timezone_id, cast(day + timedelta(days=1), TIMESTAMP))
    stmt = (
        select_clause.join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id)
            & (TariffGeneratedRate.start_time >= tz_adjusted_from_expr)
            & (TariffGeneratedRate.start_time < tz_adjusted_to_expr)
            & (TariffGeneratedRate.changed_time >= changed_after)
            & (TariffGeneratedRate.site_id == site_id)
            & (Site.aggregator_id == aggregator_id)
        )
        .offset(start)
        .limit(limit)
    )

    if not only_count:
        stmt = stmt.order_by(
            TariffGeneratedRate.start_time.asc(),
            TariffGeneratedRate.changed_time.desc(),
            TariffGeneratedRate.tariff_generated_rate_id.desc(),
        )

    resp = await session.execute(stmt)
    if only_count:
        return resp.scalar_one()
    else:
        return [_localize_start_time(rate_and_tz) for rate_and_tz in resp.all()]


async def count_tariff_rates_for_day(
    session: AsyncSession, aggregator_id: int, tariff_id: int, site_id: int, day: date, changed_after: datetime
) -> int:
    """Fetches the number of TariffGeneratedRate's stored for the specified day. Date will be assessed in the local
    timezone for the site

    changed_after: Only tariffs with a changed_time greater than this value will be counted (0 will count everything)"""

    return await _tariff_rates_for_day(
        True, session, aggregator_id, tariff_id, site_id, day, 0, changed_after, None
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def select_tariff_rates_for_day(
    session: AsyncSession,
    aggregator_id: int,
    tariff_id: int,
    site_id: int,
    day: date,
    start: int,
    changed_after: datetime,
    limit: int,
) -> Sequence[TariffGeneratedRate]:
    """Selects TariffGeneratedRate entities (with pagination) for a single tariff date. Date will be assessed in the
    local timezone for the site

    tariff_id: The parent tariff primary key
    site_id: The specific site rates are being requested for
    day: The specific day of the year to restrict the lookup of values to
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by sep2 requirements on TimeTariffInterval which is start ASC, creation DESC, id DESC"""

    return await _tariff_rates_for_day(
        False, session, aggregator_id, tariff_id, site_id, day, start, changed_after, limit
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list


async def select_tariff_rate_for_day_time(
    session: AsyncSession, aggregator_id: int, tariff_id: int, site_id: int, day: date, time_of_day: time
) -> Optional[TariffGeneratedRate]:
    """Selects single TariffGeneratedRate entity for a single tariff date / interval start. Date/time will
    be matched according to the local timezone for site

    time_of_day must be an EXACT match to return something (it's not enough to set it in the
    middle of an interval + duration)
    site_id: The specific site rates are being requested for
    tariff_id: The parent tariff primary key
    day: The specific day of the year to restrict the lookup of values to
    time_of_day: The specific time of day to find a match"""

    datetime_match = datetime.combine(day, time_of_day)

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    expr_start_at_site_tz = func.timezone(Site.timezone_id, TariffGeneratedRate.start_time)
    stmt = (
        select(TariffGeneratedRate, Site.timezone_id)
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id)
            & (expr_start_at_site_tz == datetime_match)
            & (TariffGeneratedRate.site_id == site_id)
            & (Site.aggregator_id == aggregator_id)
        )
    )

    resp = await session.execute(stmt)
    row = resp.one_or_none()
    if row is None:
        return None
    return _localize_start_time(row)


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
    single_date_counts: Sequence[
        Row[tuple[date, int]]
    ]  # each unique dates count of TariffGenerateRate instances. date ordered


async def select_rate_stats(
    session: AsyncSession, aggregator_id: int, tariff_id: int, site_id: int, changed_after: datetime
) -> TariffGeneratedRateStats:
    """Calculates some basic statistics on TariffGeneratedRate. The max/min date will be in the local timezone
    for site

    tariff_id: The parent tariff primary key
    site_id: The specific site rates are being requested for
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)"""
    expr_start_at_site_tz = func.timezone(Site.timezone_id, TariffGeneratedRate.start_time)
    stmt = (
        select(
            func.count(), func.max(expr_start_at_site_tz), func.min(expr_start_at_site_tz), func.max(Site.timezone_id)
        )  # There will only be a single tz_name due to site being 1-1 relationship
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id)
            & (TariffGeneratedRate.site_id == site_id)
            & (TariffGeneratedRate.changed_time >= changed_after)
            & (Site.aggregator_id == aggregator_id)
        )
    )

    resp = await session.execute(stmt)
    (count, max_date, min_date, tz_name) = resp.one()
    if count == 0:
        return TariffGeneratedRateStats(total_rates=count, first_rate=None, last_rate=None)
    else:
        # Adjust max/min to use site local time
        tz = ZoneInfo(tz_name)
        max_date = max_date.astimezone(tz)
        min_date = min_date.astimezone(tz)
        return TariffGeneratedRateStats(total_rates=count, first_rate=min_date, last_rate=max_date)


async def count_unique_rate_days(
    session: AsyncSession, aggregator_id: int, tariff_id: int, site_id: int, changed_after: datetime
) -> int:
    """Counts the number of unique dates (not counting the time) that a site has TariffGeneratedRate's for. The
    counted dates will be done in the local timezone for the site"""
    expr_start_at_site_tz = func.timezone(Site.timezone_id, TariffGeneratedRate.start_time)
    stmt = (
        select(func.count(distinct(cast(expr_start_at_site_tz, Date))))
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id)
            & (TariffGeneratedRate.site_id == site_id)
            & (TariffGeneratedRate.changed_time >= changed_after)
            & (Site.aggregator_id == aggregator_id)
        )
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_rate_daily_stats(
    session: AsyncSession,
    aggregator_id: int,
    tariff_id: int,
    site_id: int,
    start: int,
    changed_after: datetime,
    limit: int,
) -> TariffGeneratedRateDailyStats:
    """Fetches the aggregate totals of TariffGeneratedRate grouped by the date upon which they occurred. The occurrence
    date will be in the local timezone for the site

    Results will be ordered by date ASC"""
    expr_start_at_site_tz = func.timezone(Site.timezone_id, TariffGeneratedRate.start_time)
    stmt = (
        select(cast(expr_start_at_site_tz, Date).label("start_date"), func.count())
        .join(TariffGeneratedRate.site)
        .where(
            (TariffGeneratedRate.tariff_id == tariff_id)
            & (TariffGeneratedRate.site_id == site_id)
            & (TariffGeneratedRate.changed_time >= changed_after)
            & (Site.aggregator_id == aggregator_id)
        )
        .group_by("start_date")
        .order_by("start_date")
        .offset(start)
        .limit(limit)
    )
    resp = await session.execute(stmt)
    date_page = resp.fetchall()

    count = await count_unique_rate_days(session, aggregator_id, tariff_id, site_id, changed_after)

    return TariffGeneratedRateDailyStats(total_distinct_dates=count, single_date_counts=date_page)
