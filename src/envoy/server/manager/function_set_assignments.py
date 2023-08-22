from datetime import datetime

from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.api.request import RequestStateParameters
from envoy.server.crud import pricing
from envoy.server.mapper.sep2.function_set_assignments import FunctionSetAssignmentsMapper


class FunctionSetAssignmentsManager:
    @staticmethod
    async def fetch_function_set_assignments_for_aggregator_and_site(
        session: AsyncSession,
        request_params: RequestStateParameters,
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
        request_params: RequestStateParameters,
        site_id: int,
    ) -> FunctionSetAssignmentsListResponse:
        # At present a function sets assignments list response will only return 1 function set assignments response
        # We hard-code the fsa_id to be 1
        DEFAULT_FSA_ID = 1

        function_set_assignments = (
            await FunctionSetAssignmentsManager.fetch_function_set_assignments_for_aggregator_and_site(
                session=session, request_params=request_params, site_id=site_id, fsa_id=DEFAULT_FSA_ID
            )
        )

        return FunctionSetAssignmentsMapper.map_to_list_response(
            function_set_assignments=[function_set_assignments], site_id=site_id
        )
