from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud import pricing
from envoy.server.mapper.sep2.function_set_assignments import FunctionSetAssignmentsMapper
from envoy.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)


class FunctionSetAssignmentsManager:
    @staticmethod
    async def fetch_function_set_assignments_for_aggregator_and_site(
        session: AsyncSession,
        aggregator_id: int,
        site_id: int,
        fsa_id: int,
    ) -> FunctionSetAssignmentsResponse:
        tariff_count = await pricing.select_tariff_count(session, datetime.min)
        doe_count = 1
        return FunctionSetAssignmentsMapper.map_to_response(
            fsa_id=fsa_id, site_id=site_id, doe_count=doe_count, tariff_count=tariff_count
        )

    @staticmethod
    async def fetch_function_set_assignments_list_for_aggregator_and_site(
        session: AsyncSession,
        aggregator_id: int,
        site_id: int,
        start: int,
        limit: int,
    ) -> FunctionSetAssignmentsListResponse:
        # At present a function sets assignments list response will only return 1 function set assigments response
        # We hard-code the fsa_id to be 1
        DEFAULT_FSA_ID = 1

        function_set_assignments = (
            await FunctionSetAssignmentsManager.fetch_function_set_assignments_for_aggregator_and_site(
                session=session, aggregator_id=aggregator_id, site_id=site_id, fsa_id=DEFAULT_FSA_ID
            )
        )

        return FunctionSetAssignmentsMapper.map_to_list_response(
            function_set_assignments=[function_set_assignments], site_id=site_id
        )