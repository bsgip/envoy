from typing import Sequence

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.sep2.log_events import LogEvent, LogEventList
from envoy_schema.server.schema.sep2.pub_sub import SubscribableType

from envoy.server.mapper.common import generate_href
from envoy.server.model.site import SiteLogEvent
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope


class LogEventMapper:

    @staticmethod
    def log_event_href(scope: BaseRequestScope, site_id: int, log_event_id: int) -> str:
        return generate_href(
            uri.LogEventUri,
            scope,
            site_id=site_id,
            log_event_id=log_event_id,
        )

    @staticmethod
    def map_to_log_event(scope: BaseRequestScope, site_log_event: SiteLogEvent) -> LogEvent:
        """Generates a sep2 LogEvent for a given SiteLogEvent."""

        return LogEvent(
            href=LogEventMapper.log_event_href(scope, site_log_event.site_id, site_log_event.site_log_event_id),
            createdDateTime=int(site_log_event.created_time.timestamp()),
            details=site_log_event.details,
            extendedData=site_log_event.extended_data,
            functionSet=site_log_event.function_set,
            logEventCode=site_log_event.log_event_code,
            logEventID=site_log_event.log_event_id,
            logEventPEN=site_log_event.log_event_pen,
            profileID=site_log_event.profile_id,
        )

    @staticmethod
    def map_from_log_event(log_event: LogEvent, site_id: int) -> SiteLogEvent:
        """Maps a sep2 LogEvent to an internal SiteLogEvent model for a specific site"""

        # createdTime will be managed by the DB itself
        return SiteLogEvent(
            site_id=site_id,
            details=log_event.details,
            extended_data=log_event.extendedData,
            function_set=log_event.functionSet,
            log_event_code=log_event.logEventCode,
            log_event_id=log_event.logEventID,
            log_event_pen=log_event.logEventPEN,
            profile_id=log_event.profileID,
        )


class LogEventListMapper:

    @staticmethod
    def map_to_list_response(
        scope: DeviceOrAggregatorRequestScope,
        responses: Sequence[SiteLogEvent],
        total_responses: int,
    ) -> LogEventList:
        """Generates a list response for a set of log events"""
        return LogEventList(
            href=generate_href(uri.LogEventListUri, scope, site_id=scope.display_site_id),
            subscribable=SubscribableType.resource_does_not_support_subscriptions,
            all_=total_responses,
            results=len(responses),
            LogEvent_=[LogEventMapper.map_to_log_event(scope, r) for r in responses],
        )
