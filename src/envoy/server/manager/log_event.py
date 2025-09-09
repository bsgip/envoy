import logging
from datetime import datetime

from envoy_schema.server.schema.sep2.log_events import LogEvent, LogEventList
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.site import select_single_site_with_site_id
from envoy.server.crud.log_event import count_site_log_events, select_log_event_for_scope, select_site_log_events
from envoy.server.exception import NotFoundError
from envoy.server.mapper.sep2.log_event import LogEventListMapper, LogEventMapper
from envoy.server.request_scope import DeviceOrAggregatorRequestScope, SiteRequestScope

logger = logging.getLogger(__name__)


class LogEventManager:

    @staticmethod
    async def fetch_log_event_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        log_event_id: int,
    ) -> LogEvent:
        """Fetches a LogEvent by id for a specific scope. Failure to find the response will raise a NotFoundError."""
        site_log_event = await select_log_event_for_scope(session, scope.aggregator_id, scope.site_id, log_event_id)
        if site_log_event is None:
            raise NotFoundError(f"LogEvent {log_event_id} either doesn't exist or is inaccessible in this scope")
        return LogEventMapper.map_to_log_event(scope, site_log_event)

    @staticmethod
    async def fetch_log_event_list_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        start: int,
        limit: int,
        after: datetime,
    ) -> LogEventList:
        """Fetches a LogEventList for a specific scope. Results will be filtered according to the start/limit/after
        parameters and ordered according to sep2 LogEvent ordering."""
        total_logs = await count_site_log_events(session, scope.aggregator_id, scope.site_id, after)
        logs = await select_site_log_events(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            start=start,
            limit=limit,
            created_after=after,
        )
        return LogEventListMapper.map_to_list_response(scope, logs, total_logs)

    @staticmethod
    async def create_log_event_for_scope(session: AsyncSession, scope: SiteRequestScope, log_event: LogEvent) -> str:
        """Creates a new LogEvent entry in the database.

        Raises NotFoundError if the requested site doesn't exist in this scope.

        Returns the href associated with the new LogEvent entity
        """

        # Validate the referenced doe is accessible to this scope
        existing_site = await select_single_site_with_site_id(
            session, aggregator_id=scope.aggregator_id, site_id=scope.site_id
        )
        if existing_site is None:
            raise NotFoundError(f"EndDevice '{scope.site_id}' is inaccessible / doesn't exist.")

        site_log_event = LogEventMapper.map_from_log_event(log_event, existing_site.site_id)

        # Once we commit, the object becomes mostly detached and can't be referenced. So we need to do any
        # remaining operations on it between flush and commit
        session.add(site_log_event)
        await session.flush()
        href = LogEventMapper.log_event_href(scope, existing_site.site_id, site_log_event.site_log_event_id)
        await session.commit()

        return href
