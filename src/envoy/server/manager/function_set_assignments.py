from datetime import datetime
from itertools import chain
from typing import Optional

from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.doe import select_site_control_group_fsa_ids
from envoy.server.crud.pricing import select_tariff_fsa_ids
from envoy.server.crud.site import select_single_site_with_site_id
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.mapper.sep2.function_set_assignments import FunctionSetAssignmentsMapper
from envoy.server.request_scope import SiteRequestScope


class FunctionSetAssignmentsManager:
    @staticmethod
    async def fetch_function_set_assignments_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        fsa_id: int,
    ) -> Optional[FunctionSetAssignmentsResponse]:
        site = await select_single_site_with_site_id(
            session=session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
        )
        if site is None:
            return None

        # Check that our FSA ID exists somewhere in the DB
        if (fsa_id not in await select_site_control_group_fsa_ids(session, datetime.min)) and (
            fsa_id not in await select_tariff_fsa_ids(session, datetime.min)
        ):
            return None

        return FunctionSetAssignmentsMapper.map_to_response(scope=scope, fsa_id=fsa_id)

    @staticmethod
    async def fetch_distinct_function_set_assignment_ids(session: AsyncSession, changed_after: datetime) -> list[int]:
        site_control_fsa_ids = await select_site_control_group_fsa_ids(session, changed_after)
        tariff_fsa_ids = await select_tariff_fsa_ids(session, changed_after)
        return sorted(set(chain(site_control_fsa_ids, tariff_fsa_ids)))

    @staticmethod
    async def fetch_function_set_assignments_list_for_scope(
        session: AsyncSession,
        scope: SiteRequestScope,
        start: int,
        limit: int,
        changed_after: datetime,
    ) -> Optional[FunctionSetAssignmentsListResponse]:

        site = await select_single_site_with_site_id(
            session=session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
        )
        if site is None:
            return None

        # Combine the IDs into a sorted, distinct list
        distinct_fsa_ids = await FunctionSetAssignmentsManager.fetch_distinct_function_set_assignment_ids(
            session, changed_after
        )
        end_index = start + limit
        paginated_fsa_ids = distinct_fsa_ids[start:end_index]

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return FunctionSetAssignmentsMapper.map_to_list_response(
            scope=scope,
            fsa_ids=paginated_fsa_ids,
            total_fsa_ids=len(distinct_fsa_ids),
            pollrate_seconds=config.fsal_pollrate_seconds,
        )
