from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.der import (
    DefaultDERControl,
    DERControlListResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.doe import (
    count_active_does_include_deleted,
    count_does_at_timestamp,
    select_active_does_include_deleted,
    select_doe_include_deleted,
    select_does_at_timestamp,
)
from envoy.server.crud.end_device import select_single_site_with_site_id, select_site_with_default_site_control
from envoy.server.exception import NotFoundError
from envoy.server.manager.time import utc_now
from envoy.server.mapper.csip_aus.doe import (
    DERControlListSource,
    DERControlMapper,
    DERControlResponse,
    DERProgramMapper,
)
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import DefaultSiteControl
from envoy.server.request_scope import SiteRequestScope


class DERProgramManager:
    @staticmethod
    async def fetch_list_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        default_doe: Optional[DefaultDoeConfiguration],
    ) -> DERProgramListResponse:
        """Program lists are static - this will just return a single fixed Dynamic Operating Envelope Program

        if site_id DNE or is inaccessible to aggregator_id a NotFoundError will be raised"""

        site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        now = utc_now()
        total_does = await count_active_does_include_deleted(session, site, now, datetime.min)

        # Note that the actual site_id is used to construct the response as it is required for the href
        return DERProgramMapper.doe_program_list_response(scope, total_does, default_doe)

    @staticmethod
    async def fetch_doe_program_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        default_doe: Optional[DefaultDoeConfiguration],
    ) -> DERProgramResponse:
        """DOE Programs are static - this will just return a fixed Dynamic Operating Envelope Program

        if site_id DNE is inaccessible to aggregator_id a NotFoundError will be raised"""

        site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        now = utc_now()
        total_does = await count_active_does_include_deleted(session, site, now, datetime.min)
        return DERProgramMapper.doe_program_response(scope, total_does, default_doe)


class DERControlManager:
    @staticmethod
    async def fetch_doe_control_for_scope(
        session: AsyncSession, scope: SiteRequestScope, doe_id: int
    ) -> Optional[DERControlResponse]:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a lookup for a
        particular DOE by ID but ensuring it stays scoped to the appropriate request"""
        doe = await select_doe_include_deleted(session, scope.aggregator_id, scope.site_id, doe_id)
        if doe is None:
            return None

        return DERControlMapper.map_to_response(scope, doe)

    @staticmethod
    async def fetch_doe_controls_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> DERControlListResponse:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a pagination API
        for iterating DOE's stored against a particular site"""

        now = utc_now()

        site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        does: list[DynamicOperatingEnvelope | ArchiveDynamicOperatingEnvelope]
        total_count: int
        if site:
            # site is accessible to the current scope - perform fetch query
            does = await select_active_does_include_deleted(session, site, now, start, changed_after, limit)
            total_count = await count_active_does_include_deleted(session, site, now, changed_after)
        else:
            # Site isn't in scope - return empty list
            does = []
            total_count = 0
        return DERControlMapper.map_to_list_response(scope, does, total_count, DERControlListSource.DER_CONTROL_LIST)

    @staticmethod
    async def fetch_active_doe_controls_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
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
        site = await select_site_with_default_site_control(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        default_site_control = DERControlManager._resolve_default_site_control(default_doe, site.default_site_control)
        if default_site_control is None:
            raise NotFoundError(f"There is no default DefaultDERControl configured for site {scope.site_id}")
        return DERControlMapper.map_to_default_response(scope, default_site_control)

    @staticmethod
    def _resolve_default_site_control(
        default_doe: Optional[DefaultDoeConfiguration],
        default_site_control: Optional[DefaultSiteControl] = None,
    ) -> Optional[DefaultSiteControl]:
        """Construct DefaultSiteControl with optional fields filled using the global DefaultDoeConfiguration"""

        if default_doe is None:
            return default_site_control

        if default_site_control is not None:
            return DefaultSiteControl(
                import_limit_active_watts=default_site_control.import_limit_active_watts
                or default_doe.import_limit_active_watts,
                export_limit_active_watts=default_site_control.export_limit_active_watts
                or default_doe.export_limit_active_watts,
                generation_limit_active_watts=default_site_control.generation_limit_active_watts
                or default_doe.generation_limit_active_watts,
                load_limit_active_watts=default_site_control.load_limit_active_watts
                or default_doe.load_limit_active_watts,
                ramp_rate_percent_per_second=default_site_control.ramp_rate_percent_per_second
                or default_doe.ramp_rate_percent_per_second,
            )
        return DefaultSiteControl(
            import_limit_active_watts=default_doe.import_limit_active_watts,
            export_limit_active_watts=default_doe.export_limit_active_watts,
            generation_limit_active_watts=default_doe.generation_limit_active_watts,
            load_limit_active_watts=default_doe.load_limit_active_watts,
            ramp_rate_percent_per_second=default_doe.ramp_rate_percent_per_second,
        )
