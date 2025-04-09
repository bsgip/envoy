from datetime import date, datetime, timedelta
from typing import Optional, Sequence, Union

from sqlalchemy import TIMESTAMP, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.common import localize_start_time, localize_start_time_for_entity
from envoy.server.model.doe import DynamicOperatingEnvelope as DOE
from envoy.server.model.site import Site


async def select_doe_for_scope(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    doe_id: int,
) -> Optional[DOE]:
    """Attempts to fetch a doe using its' DOE id, also scoping it to a particular aggregator/site

    aggregator_id: The aggregator id to constrain the lookup to
    site_id: If None - no effect otherwise the query will apply a filter on site_id using this value"""

    stmt = (
        select(DOE, Site.timezone_id)
        .join(DOE.site)
        .where((DOE.dynamic_operating_envelope_id == doe_id) & (Site.aggregator_id == aggregator_id))
    )
    if site_id is not None:
        stmt = stmt.where(DOE.site_id == site_id)

    resp = await session.execute(stmt)
    raw = resp.one_or_none()
    if raw is None:
        return None
    return localize_start_time(raw)


async def _does_at_timestamp(
    is_counting: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    timestamp: datetime,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[DOE], int]:
    """Internal utility for fetching doe's that are active for the specific timestamp

    site_id: If None - no site_id filter applied, otherwise filter on site_id = Value

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    select_clause: Union[Select[tuple[int]], Select[tuple[DOE, str]]]
    if is_counting:
        select_clause = select(func.count()).select_from(DOE)
    else:
        select_clause = select(DOE, Site.timezone_id)

    one_second = timedelta(seconds=1)

    # fmt: off
    stmt = (
        select_clause
        .join(DOE.site)
        .where(
            (DOE.start_time <= timestamp) &
            (DOE.start_time + (DOE.duration_seconds * one_second) > timestamp) &
            (Site.aggregator_id == aggregator_id))
        .offset(start)
        .limit(limit)
    )
    # fmt: on

    if changed_after != datetime.min:
        stmt = stmt.where((DOE.changed_time >= changed_after))

    if site_id is not None:
        stmt = stmt.where(DOE.site_id == site_id)

    if not is_counting:
        stmt = stmt.order_by(DOE.start_time.asc(), DOE.changed_time.desc(), DOE.dynamic_operating_envelope_id.desc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return [localize_start_time(doe_and_tz) for doe_and_tz in resp.all()]


async def _site_does_for_day(
    is_counting: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: int,
    day: Optional[date],
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[DOE], int]:
    """Internal utility for fetching doe's for a specific day (if specified) for a single site that either counts or
    returns the entities

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC

    Where the site_id is None, all sites for the aggregator will be considered."""

    # Discovering the timezone BEFORE making the query will allow the better use of indexes
    site_timezone_id = (
        await session.execute(
            select(Site.timezone_id).where((Site.site_id == site_id) & (Site.aggregator_id == aggregator_id))
        )
    ).scalar_one_or_none()
    if not site_timezone_id:
        if is_counting:
            return 0
        else:
            return []

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    select_clause: Union[Select[tuple[int]], Select[tuple[DOE, str]]]
    if is_counting:
        select_clause = select(func.count()).select_from(DOE)
    else:
        select_clause = select(DOE)

    stmt = select_clause.where((DOE.site_id == site_id)).offset(start).limit(limit)

    if changed_after != datetime.min:
        stmt = stmt.where((DOE.changed_time >= changed_after))

    # To best utilise the doe indexes - we map our literal start/end times to the site local time zone
    if day:
        tz_adjusted_from_expr = func.timezone(site_timezone_id, cast(day, TIMESTAMP))
        tz_adjusted_to_expr = func.timezone(site_timezone_id, cast(day + timedelta(days=1), TIMESTAMP))
        stmt = stmt.where((DOE.start_time >= tz_adjusted_from_expr) & (DOE.start_time < tz_adjusted_to_expr))

    if not is_counting:
        stmt = stmt.order_by(DOE.start_time.asc(), DOE.changed_time.desc(), DOE.dynamic_operating_envelope_id.desc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return [localize_start_time_for_entity(doe, site_timezone_id) for doe in resp.scalars()]


async def _aggregator_does_for_day(
    is_counting: bool,
    session: AsyncSession,
    aggregator_id: int,
    day: Optional[date],
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[DOE], int]:
    """Internal utility for fetching doe's for a specific day (if specified) that either counts or returns the entities

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC

    Where the site_id is None, all sites for the aggregator will be considered."""

    # At the moment tariff's are exposed to all aggregators - the plan is for them to be scoped for individual
    # groups of sites but this could be subject to change as the DNSP's requirements become more clear
    select_clause: Union[Select[tuple[int]], Select[tuple[DOE, str]]]
    if is_counting:
        select_clause = select(func.count()).select_from(DOE)
    else:
        select_clause = select(DOE, Site.timezone_id)

    stmt = select_clause.join(DOE.site).where(Site.aggregator_id == aggregator_id).offset(start).limit(limit)

    if changed_after != datetime.min:
        stmt = stmt.where((DOE.changed_time >= changed_after))

    # To best utilise the doe indexes - we map our literal start/end times to the site local time zone
    if day:
        tz_adjusted_from_expr = func.timezone(Site.timezone_id, cast(day, TIMESTAMP))
        tz_adjusted_to_expr = func.timezone(Site.timezone_id, cast(day + timedelta(days=1), TIMESTAMP))
        stmt = stmt.where((DOE.start_time >= tz_adjusted_from_expr) & (DOE.start_time < tz_adjusted_to_expr))

    if not is_counting:
        stmt = stmt.order_by(DOE.start_time.asc(), DOE.changed_time.desc(), DOE.dynamic_operating_envelope_id.desc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return [localize_start_time(doe_and_tz) for doe_and_tz in resp.all()]


async def count_does(session: AsyncSession, aggregator_id: int, site_id: Optional[int], changed_after: datetime) -> int:
    """Fetches the number of DynamicOperatingEnvelope's stored. Date will be assessed in the local timezone for the site

    changed_after: Only doe's with a changed_time greater than this value will be counted (0 will count everything)"""

    if site_id is None:
        return await _aggregator_does_for_day(
            True, session, aggregator_id, None, 0, changed_after, None
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an int count
    else:
        return await _site_does_for_day(
            True, session, aggregator_id, site_id, None, 0, changed_after, None
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an int count


async def select_does(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], start: int, changed_after: datetime, limit: int
) -> Sequence[DOE]:
    """Selects DynamicOperatingEnvelope entities (with pagination). Date will be assessed in the local
    timezone for the site

    site_id: The specific site does are being requested for
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    if site_id is None:
        return await _aggregator_does_for_day(
            False, session, aggregator_id, None, start, changed_after, limit
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list
    else:
        return await _site_does_for_day(
            False, session, aggregator_id, site_id, None, start, changed_after, limit
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list


async def count_does_for_day(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], day: date, changed_after: datetime
) -> int:
    """Fetches the number of DynamicOperatingEnvelope's stored for the specified day. Date will be assessed in the local
    timezone for the site

    changed_after: Only doe's with a changed_time greater than this value will be counted (0 will count everything)"""

    if site_id is None:
        return await _aggregator_does_for_day(
            True, session, aggregator_id, day, 0, changed_after, None
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an int count
    else:
        return await _site_does_for_day(
            True, session, aggregator_id, site_id, day, 0, changed_after, None
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an int count


async def select_does_for_day(
    session: AsyncSession, aggregator_id: int, site_id: int, day: date, start: int, changed_after: datetime, limit: int
) -> Sequence[DOE]:
    """Selects DynamicOperatingEnvelope entities (with pagination) for a single date. Date will be assessed in the
    local timezone for the site

    site_id: The specific site does are being requested for
    day: The specific day of the year to restrict the lookup of values to
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    if site_id is None:
        return await _aggregator_does_for_day(
            False, session, aggregator_id, day, start, changed_after, limit
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list
    else:
        return await _site_does_for_day(
            False, session, aggregator_id, site_id, day, start, changed_after, limit
        )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list


async def count_does_at_timestamp(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], timestamp: datetime, changed_after: datetime
) -> int:
    """Fetches the number of DynamicOperatingEnvelope's stored that contain timestamp.

    aggregator_id: The aggregator ID to filter sites/does against
    site_id: If None, no filter on site_id otherwise filters the results to this specific site_id
    timestamp: The actual timestamp that a DOE range must contain in order to be considered
    changed_after: Only doe's with a changed_time greater than this value will be counted (0 will count everything)"""

    return await _does_at_timestamp(
        True, session, aggregator_id, site_id, timestamp, 0, changed_after, None
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list


async def select_does_at_timestamp(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    timestamp: datetime,
    start: int,
    changed_after: datetime,
    limit: int,
) -> Sequence[DOE]:
    """Selects DynamicOperatingEnvelope entities (with pagination) that contain timestamp. Date will be assessed in the
    local timezone for the site

    aggregator_id: The aggregator ID to filter sites/does against
    site_id: If None, no filter on site_id otherwise filters the results to this specific site_id
    timestamp: The actual timestamp that a DOE range must contain in order to be considered
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    return await _does_at_timestamp(
        False, session, aggregator_id, site_id, timestamp, start, changed_after, limit
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list
