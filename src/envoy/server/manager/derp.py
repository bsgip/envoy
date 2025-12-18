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
    count_site_control_groups,
    select_active_does_include_deleted,
    select_doe_include_deleted,
    select_does_at_timestamp,
    select_site_control_group_by_id,
    select_site_control_groups,
)
from envoy.server.crud.site import select_single_site_with_site_id
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
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup, SiteControlGroupDefault
from envoy.server.request_scope import SiteRequestScope


class DERProgramManager:
    @staticmethod
    async def fetch_list_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        start: int,
        changed_after: datetime,
        limit: int,
        fsa_id: Optional[int],
    ) -> DERProgramListResponse:
        """Returns the list of DERPrograms accessible to a site. This can optionally filter programs to a specific
        function set assignment ID (fsa_id)

        if site_id DNE or is inaccessible to aggregator_id a NotFoundError will be raised"""

        now = utc_now()

        site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        config = await RuntimeServerConfigManager.fetch_current_config(session)

        site_control_groups = await select_site_control_groups(
            session, start=start, limit=limit, changed_after=changed_after, fsa_id=fsa_id, include_defaults=True
        )
        site_control_group_count = await count_site_control_groups(session, changed_after, fsa_id=fsa_id)
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
            config.derpl_pollrate_seconds,
            fsa_id,
        )

    @staticmethod
    async def fetch_doe_program_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        der_program_id: int,
    ) -> DERProgramResponse:
        """Returns the DERProgram with the specified ID

        if site_id DNE is inaccessible to aggregator_id a NotFoundError will be raised"""

        site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {scope.site_id} is not accessible / does not exist")

        site_control_group = await select_site_control_group_by_id(session, der_program_id, include_default=True)
        if not site_control_group:
            raise NotFoundError(f"der_program_id {der_program_id} is not accessible / does not exist")

        now = utc_now()
        total_does = await count_active_does_include_deleted(session, der_program_id, site, now, datetime.min)
        return DERProgramMapper.doe_program_response(
            scope, total_does, site_control_group, site_control_group.site_control_group_default
        )


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
    async def fetch_default_doe_controls_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        der_program_id: int,
    ) -> DefaultDERControl:
        """Returns a default DOE control for DERProgram - raises an error if the referenced DERProgram DNE"""

        scg = await select_site_control_group_by_id(session, der_program_id, include_default=True)
        if not scg:
            raise NotFoundError(f"DERProgram {der_program_id} for site {scope.site_id} is not accessible / missing.")

        scg_default = scg.site_control_group_default
        if scg_default is None:
            scg_default = SiteControlGroupDefault(
                site_control_group_default_id=0,
                site_control_group_id=scg.site_control_group_id,
                created_time=scg.created_time,
                changed_time=scg.created_time,  # This is deliberately set to created_time instead of changed_time
                version=0,
            )

        config = await RuntimeServerConfigManager.fetch_current_config(session)
        return DERControlMapper.map_to_default_response(
            scope,
            scg_default,
            scope.display_site_id,
            der_program_id,
            config.site_control_pow10_encoding,
        )
