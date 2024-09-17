from datetime import date, datetime
from typing import Optional

from envoy_schema.server.schema.sep2.der import (
    DefaultDERControl,
    DERControlListResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.doe import (
    count_does,
    count_does_at_timestamp,
    count_does_for_day,
    select_doe_for_scope,
    select_does,
    select_does_at_timestamp,
    select_does_for_day,
)
from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.exception import NotFoundError
from envoy.server.manager.time import utc_now
from envoy.server.mapper.csip_aus.doe import (
    DERControlListSource,
    DERControlMapper,
    DERControlResponse,
    DERProgramMapper,
)
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.request_scope import DeviceOrAggregatorRequestScope, SiteRequestScope


class DERProgramManager:
    @staticmethod
    async def fetch_list_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        default_doe: Optional[DefaultDoeConfiguration],
    ) -> DERProgramListResponse:
        """Program lists are static - this will just return a single fixed Dynamic Operating Envelope Program

        if site_id DNE or is inaccessible to aggregator_id a NotFoundError will be raised"""

        if scope.site_id is not None:
            site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
            if not site:
                raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        total_does = await count_does(session, scope.aggregator_id, scope.site_id, datetime.min)
        # Note that the actual site_id is used to construct the response as it is required for the href
        return DERProgramMapper.doe_program_list_response(scope, total_does, default_doe)

    @staticmethod
    async def fetch_doe_program_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        default_doe: Optional[DefaultDoeConfiguration],
    ) -> DERProgramResponse:
        """DOE Programs are static - this will just return a fixed Dynamic Operating Envelope Program

        if site_id DNE is inaccessible to aggregator_id a NotFoundError will be raised"""
        if scope.site_id is not None:
            site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
            if not site:
                raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        total_does = await count_does(session, scope.aggregator_id, scope.site_id, datetime.min)
        return DERProgramMapper.doe_program_response(scope, total_does, default_doe)


class DERControlManager:
    @staticmethod
    async def fetch_doe_control_for_scope(
        session: AsyncSession, scope: DeviceOrAggregatorRequestScope, doe_id: int
    ) -> Optional[DERControlResponse]:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a lookup for a
        particular DOE by ID but ensuring it stays scoped to the appropriate request"""
        doe = await select_doe_for_scope(session, scope.aggregator_id, scope.site_id, doe_id)
        if doe is None:
            return None

        return DERControlMapper.map_to_response(scope, doe)

    @staticmethod
    async def fetch_doe_controls_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> DERControlListResponse:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a pagination API
        for iterating DOE's stored against a particular site"""
        does = await select_does(session, scope.aggregator_id, scope.site_id, start, changed_after, limit)
        total_count = await count_does(session, scope.aggregator_id, scope.site_id, changed_after)
        return DERControlMapper.map_to_list_response(scope, does, total_count, DERControlListSource.DER_CONTROL_LIST)

    @staticmethod
    async def fetch_active_doe_controls_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> DERControlListResponse:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a pagination API
        for iterating active DOE's (i.e their timerange intersects with now) stored against a particular site"""

        now = utc_now()
        does = await select_does_at_timestamp(
            session, scope.aggregator_id, scope.site_id, now, start, changed_after, limit
        )
        total_count = await count_does_at_timestamp(session, scope.aggregator_id, scope.site_id, now, changed_after)
        return DERControlMapper.map_to_list_response(
            scope, does, total_count, DERControlListSource.ACTIVE_DER_CONTROL_LIST
        )

    @staticmethod
    async def fetch_default_doe_controls_for_site(
        session: AsyncSession,
        scope: SiteRequestScope,
        default_doe: Optional[DefaultDoeConfiguration],
    ) -> DefaultDERControl:
        """Returns a default DOE control for a site or raises a NotFoundError if the site / defaults are inaccessible
        or not configured"""
        site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        if not default_doe:
            raise NotFoundError(f"There is no default DERControl configured for site {scope.site_id}")

        return DERControlMapper.map_to_default_response(default_doe)

    @staticmethod
    async def fetch_doe_controls_for_scope_day(
        session: AsyncSession,
        scope: SiteRequestScope,
        day: date,
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> DERControlListResponse:
        """Similar to fetch_doe_controls_for_site but filtered to a specific day (in site local time)"""

        does = await select_does_for_day(session, scope.aggregator_id, scope.site_id, day, start, changed_after, limit)
        total_count = await count_does_for_day(session, scope.aggregator_id, scope.site_id, day, changed_after)
        return DERControlMapper.map_to_list_response(scope, does, total_count, DERControlListSource.DER_CONTROL_LIST)
