from datetime import date, datetime, timedelta
from typing import Optional, Union
from zoneinfo import ZoneInfo

from sqlalchemy import TIMESTAMP, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.doe import DynamicOperatingEnvelope as DOE
from envoy.server.model.site import Site


def _localize_start_time(rate_and_tz: Optional[tuple[DOE, str]]) -> Optional[DOE]:
    """Localizes a DynamicOperatingEnvelope.start_time to be in the local timezone passed in as the second
    element in the tuple. Returns the DynamicOperatingEnvelope (it will be modified in place)"""
    if rate_and_tz is None:
        return None

    (rate, tz_name) = rate_and_tz
    tz = ZoneInfo(tz_name)
    rate.start_time = rate.start_time.astimezone(tz)
    return rate


async def _does_for_day(
    is_counting: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: int,
    day: Optional[date],
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[list[DOE], int]:
    """Internal utility for fetching doe's for a specific day (if specified) that either counts or returns the entities

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    if is_counting:
        select_clause = select(DOE.dynamic_operating_envelope_id)
    else:
        select_clause = select(DOE, Site.timezone_id)

    # fmt: off
    stmt = (
        select_clause
        .join(DOE.site)
        .where(
            (DOE.changed_time >= changed_after) &
            (DOE.site_id == site_id) &
            (Site.aggregator_id == aggregator_id))
        .offset(start)
        .limit(limit)
        .order_by(
            DOE.start_time.asc(),
            DOE.changed_time.desc(),
            DOE.dynamic_operating_envelope_id.desc())
    )
    # fmt: on

    # To best utilise the doe indexes - we map our literal start/end times to the site local time zone
    if day:
        tz_adjusted_from_expr = func.timezone(Site.timezone_id, cast(day, TIMESTAMP))
        tz_adjusted_to_expr = func.timezone(Site.timezone_id, cast(day + timedelta(days=1), TIMESTAMP))
        stmt = stmt.where((DOE.start_time >= tz_adjusted_from_expr) & (DOE.start_time < tz_adjusted_to_expr))

    if is_counting:
        stmt = select(func.count()).select_from(stmt)
    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return [_localize_start_time(doe_and_tz) for doe_and_tz in resp.all()]


async def count_does(session: AsyncSession, aggregator_id: int, site_id: int, changed_after: datetime) -> int:
    """Fetches the number of DynamicOperatingEnvelope's stored. Date will be assessed in the local timezone for the site

    changed_after: Only doe's with a changed_time greater than this value will be counted (0 will count everything)"""

    return await _does_for_day(True, session, aggregator_id, site_id, None, 0, changed_after, None)


async def select_does(
    session: AsyncSession, aggregator_id: int, site_id: int, start: int, changed_after: datetime, limit: int
) -> list[DOE]:
    """Selects DynamicOperatingEnvelope entities (with pagination). Date will be assessed in the local
    timezone for the site

    site_id: The specific site rates are being requested for
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    return await _does_for_day(False, session, aggregator_id, site_id, None, start, changed_after, limit)


async def count_does_for_day(
    session: AsyncSession, aggregator_id: int, site_id: int, day: date, changed_after: datetime
) -> int:
    """Fetches the number of DynamicOperatingEnvelope's stored for the specified day. Date will be assessed in the local
    timezone for the site

    changed_after: Only doe's with a changed_time greater than this value will be counted (0 will count everything)"""

    return await _does_for_day(True, session, aggregator_id, site_id, day, 0, changed_after, None)


async def select_does_for_day(
    session: AsyncSession, aggregator_id: int, site_id: int, day: date, start: int, changed_after: datetime, limit: int
) -> list[DOE]:
    """Selects DynamicOperatingEnvelope entities (with pagination) for a single date. Date will be assessed in the
    local timezone for the site

    site_id: The specific site rates are being requested for
    day: The specific day of the year to restrict the lookup of values to
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    return await _does_for_day(False, session, aggregator_id, site_id, day, start, changed_after, limit)
