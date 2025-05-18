from datetime import datetime
from typing import Any, Optional

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
    count_site_control_groups,
    select_active_does_include_deleted,
    select_doe_include_deleted,
    select_does_at_timestamp,
    select_site_control_group_by_id,
    select_site_control_groups,
)
from envoy.server.crud.end_device import select_single_site_with_site_id, select_site_with_default_site_control
from envoy.server.exception import NotFoundError
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.manager.time import utc_now
from envoy.server.mapper.csip_aus.doe import (
    DERControlListSource,
    DERControlMapper,
    DERControlResponse,
    DERProgramMapper,
)
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup
from envoy.server.model.site import DefaultSiteControl
from envoy.server.request_scope import SiteRequestScope


class DERProgramManager:
    @staticmethod
    async def fetch_list_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        default_doe: Optional[DefaultDoeConfiguration],
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> DERProgramListResponse:
        """Program lists are static - this will just return a single fixed Dynamic Operating Envelope Program

        if site_id DNE or is inaccessible to aggregator_id a NotFoundError will be raised"""

        now = utc_now()

        site = await select_site_with_default_site_control(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        default_site_control = DERControlManager._resolve_default_site_control(default_doe, site.default_site_control)
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        site_control_groups = await select_site_control_groups(
            session, start=start, limit=limit, changed_after=changed_after
        )
        site_control_group_count = await count_site_control_groups(session, changed_after)
        control_counts_by_group: list[tuple[SiteControlGroup, int]] = []
        for group in site_control_groups:
            control_counts_by_group.append(
                (
                    group,
                    await count_active_does_include_deleted(
                        session,
                        site_control_group_id=group.site_control_group_id,
                        site=site,
                        now=now,
                        changed_after=datetime.min,  # We want total count - don't reduce it based on changed_after
                    ),
                )
            )

        return DERProgramMapper.doe_program_list_response(
            scope,
            control_counts_by_group,
            site_control_group_count,
            default_site_control,
            config.derpl_pollrate_seconds,
        )

    @staticmethod
    async def fetch_doe_program_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        der_program_id: int,
        default_doe: Optional[DefaultDoeConfiguration],
    ) -> DERProgramResponse:
        """Returns the DERProgram with the specified ID

        if site_id DNE is inaccessible to aggregator_id a NotFoundError will be raised"""

        site = await select_site_with_default_site_control(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        default_site_control = DERControlManager._resolve_default_site_control(default_doe, site.default_site_control)

        site_control_group = await select_site_control_group_by_id(session, der_program_id)
        if not site_control_group:
            raise NotFoundError(f"der_program_id {der_program_id} is not accessible / does not exist")

        now = utc_now()
        total_does = await count_active_does_include_deleted(session, der_program_id, site, now, datetime.min)
        return DERProgramMapper.doe_program_response(scope, total_does, site_control_group, default_site_control)


class DERControlManager:
    @staticmethod
    async def fetch_doe_control_for_scope(
        session: AsyncSession, scope: SiteRequestScope, der_program_id: int, doe_id: int
    ) -> Optional[DERControlResponse]:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a lookup for a
        particular DOE by ID but ensuring it stays scoped to the appropriate request"""
        now = utc_now()
        doe = await select_doe_include_deleted(session, scope.aggregator_id, scope.site_id, doe_id)
        if doe is None or doe.site_control_group_id != der_program_id:
            return None

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return DERControlMapper.map_to_response(scope, der_program_id, doe, config.site_control_pow10_encoding, now)

    @staticmethod
    async def fetch_doe_controls_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        der_program_id: int,
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
            does = await select_active_does_include_deleted(
                session, der_program_id, site, now, start, changed_after, limit
            )
            total_count = await count_active_does_include_deleted(session, der_program_id, site, now, changed_after)
        else:
            # Site isn't in scope - return empty list
            does = []
            total_count = 0

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return DERControlMapper.map_to_list_response(
            scope,
            der_program_id,
            does,
            total_count,
            DERControlListSource.DER_CONTROL_LIST,
            config.site_control_pow10_encoding,
            now,
        )

    @staticmethod
    async def fetch_active_doe_controls_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        der_program_id: int,
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> DERControlListResponse:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a pagination API
        for iterating active DOE's (i.e their timerange intersects with now) stored against a particular site"""

        now = utc_now()
        does = await select_does_at_timestamp(
            session, der_program_id, scope.aggregator_id, scope.site_id, now, start, changed_after, limit
        )
        total_count = await count_does_at_timestamp(
            session, der_program_id, scope.aggregator_id, scope.site_id, now, changed_after
        )

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return DERControlMapper.map_to_list_response(
            scope,
            der_program_id,
            does,
            total_count,
            DERControlListSource.ACTIVE_DER_CONTROL_LIST,
            config.site_control_pow10_encoding,
            now,
        )

    @staticmethod
    async def fetch_default_doe_controls_for_site(
        session: AsyncSession,
        scope: SiteRequestScope,
        der_program_id: int,
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

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return DERControlMapper.map_to_default_response(scope, default_site_control, config.site_control_pow10_encoding)

    @staticmethod
    def _resolve_default_site_control(
        default_doe: Optional[DefaultDoeConfiguration],
        default_site_control: Optional[DefaultSiteControl],
    ) -> Optional[DefaultSiteControl]:
        """
        Coalesce site control entity with fallback configuration values. For each field, the
        entity's non-None value takes precedence, otherwise the fallback configuration value is used.

        Args:
            default_doe (Optional[DefaultDoeConfiguration]): Fallback configuration
                providing default values.
            default_site_control (Optional[DefaultSiteControl]): Site control entity
                loaded from the database whose non-None fields take precedence.

        Returns:
            Optional[DefaultSiteControl]: DefaultSiteControl instance with values
            coalesced from entity and fallback configuration. Returns None if both inputs are None.
        """

        def _prefer_left(left: Any, right: Any) -> Any:
            return left if left is not None else right

        if default_doe is None:
            return default_site_control

        if default_site_control is not None:
            return DefaultSiteControl(
                import_limit_active_watts=_prefer_left(
                    default_site_control.import_limit_active_watts, default_doe.import_limit_active_watts
                ),
                export_limit_active_watts=_prefer_left(
                    default_site_control.export_limit_active_watts, default_doe.export_limit_active_watts
                ),
                generation_limit_active_watts=_prefer_left(
                    default_site_control.generation_limit_active_watts, default_doe.generation_limit_active_watts
                ),
                load_limit_active_watts=_prefer_left(
                    default_site_control.load_limit_active_watts, default_doe.load_limit_active_watts
                ),
                ramp_rate_percent_per_second=_prefer_left(
                    default_site_control.ramp_rate_percent_per_second, default_doe.ramp_rate_percent_per_second
                ),
            )
        return DefaultSiteControl(
            import_limit_active_watts=default_doe.import_limit_active_watts,
            export_limit_active_watts=default_doe.export_limit_active_watts,
            generation_limit_active_watts=default_doe.generation_limit_active_watts,
            load_limit_active_watts=default_doe.load_limit_active_watts,
            ramp_rate_percent_per_second=default_doe.ramp_rate_percent_per_second,
        )
