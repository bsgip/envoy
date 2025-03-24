from datetime import datetime
from typing import Optional, Sequence, Union

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site import Site, SiteLogEvent


async def select_log_event_for_scope(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    site_log_event_id: int,
) -> Optional[SiteLogEvent]:
    """Attempts to fetch a SiteLogEvent using its' primary key, also scoping it to a particular aggregator/site

    Will NOT populate the "site" relationship

    aggregator_id: The aggregator id to constrain the lookup to
    site_id: If None - no effect otherwise the query will apply a filter on site_id using this value"""

    stmt = (
        select(SiteLogEvent)
        .join(SiteLogEvent.site)
        .where((SiteLogEvent.site_log_event_id == site_log_event_id) & (Site.aggregator_id == aggregator_id))
    )
    if site_id is not None:
        stmt = stmt.where(SiteLogEvent.site_id == site_id)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def _log_responses(
    is_counting: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    start: int,
    limit: Optional[int],
    created_after: datetime,
) -> Union[Sequence[SiteLogEvent], int]:
    """Internal utility for fetching SiteLogEvent responses

    site_id: If None - no site_id filter applied, otherwise filter on site_id = Value

    Orders by 2030.5 requirements on LogEvent which is created DESC, LogEventID DESC"""

    select_clause: Union[Select[tuple[int]], Select[tuple[SiteLogEvent]]]
    if is_counting:
        select_clause = select(func.count()).select_from(SiteLogEvent)
    else:
        select_clause = select(SiteLogEvent)

    # fmt: off
    stmt = (
        select_clause
        .join(SiteLogEvent.site)
        .where(
            (SiteLogEvent.created_time >= created_after) &
            (Site.aggregator_id == aggregator_id))
        .offset(start)
        .limit(limit)
    )
    # fmt: on

    if site_id is not None:
        stmt = stmt.where(SiteLogEvent.site_id == site_id)

    if not is_counting:
        stmt = stmt.order_by(SiteLogEvent.created_time.desc(), SiteLogEvent.log_event_id.desc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def count_site_log_events(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], created_after: datetime
) -> int:
    """Fetches the number of SiteLogEvent's stored.

    created_after: Only logs with a created_time greater than this value will be counted (0 will count everything)
    """

    return await _log_responses(
        True, session, aggregator_id, site_id, 0, None, created_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def select_site_log_events(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], start: int, limit: int, created_after: datetime
) -> Sequence[SiteLogEvent]:
    """Selects SiteLogEvent entities (with pagination).

    site_id: The specific site log events are being requested for
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    created_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on LogEvent which is created DESC, logEventID DESC"""

    return await _log_responses(
        False, session, aggregator_id, site_id, start, limit, created_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list
