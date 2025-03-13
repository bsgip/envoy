import logging
from datetime import datetime
from itertools import islice

from envoy_schema.server.schema.sep2.response import Response, ResponseListResponse, ResponseSet, ResponseSetList
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.response import (
    count_doe_responses,
    count_tariff_generated_rate_responses,
    select_doe_response_for_scope,
    select_doe_responses,
    select_rate_response_for_scope,
    select_tariff_generated_rate_responses,
)
from envoy.server.exception import NotFoundError
from envoy.server.mapper.sep2.mrid import ResponseSetType
from envoy.server.mapper.sep2.response import ResponseListMapper, ResponseMapper, ResponseSetMapper
from envoy.server.request_scope import DeviceOrAggregatorRequestScope

logger = logging.getLogger(__name__)


class ResponseManager:

    @staticmethod
    def fetch_response_set_for_scope(
        scope: DeviceOrAggregatorRequestScope, response_set_type: ResponseSetType
    ) -> ResponseSet:
        """Returns the "virtual" response set for the specific response_set_type"""
        return ResponseSetMapper.map_to_set_response(scope, response_set_type)

    @staticmethod
    def fetch_response_set_list_for_scope(
        scope: DeviceOrAggregatorRequestScope, start: int, limit: int
    ) -> ResponseSetList:
        """Provides a list view of the "virtual" response sets available for any given scope"""

        # "Paginate" the enum that backs all of our response sets
        response_sets = [
            ResponseManager.fetch_response_set_for_scope(scope, rst)
            for rst in islice(ResponseSetType, start, (start + limit))
        ]
        total_response_sets = len(ResponseSetType)

        return ResponseSetMapper.map_to_list_response(scope, response_sets, total_response_sets)

    @staticmethod
    async def fetch_response_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        response_set_type: ResponseSetType,
        response_id: int,
    ) -> Response:
        """Fetches a Response by id for a specific response set. Failure to find the response will raise a
        NotFoundError."""
        if response_set_type == ResponseSetType.DYNAMIC_OPERATING_ENVELOPES:
            doe_response = await select_doe_response_for_scope(session, scope.aggregator_id, scope.site_id, response_id)
            if doe_response is not None:
                return ResponseMapper.map_to_doe_response(scope, doe_response)
        elif response_set_type == ResponseSetType.TARIFF_GENERATED_RATES:
            tariff_response = await select_rate_response_for_scope(
                session, scope.aggregator_id, scope.site_id, response_id
            )
            if tariff_response is not None:
                return ResponseMapper.map_to_price_response(scope, tariff_response)

        raise NotFoundError(
            f"Response {response_id} for {response_set_type} either doesn't exist or is inaccessible in this scope"
        )

    @staticmethod
    async def fetch_response_list_for_scope(
        session: AsyncSession,
        scope: DeviceOrAggregatorRequestScope,
        response_set_type: ResponseSetType,
        start: int,
        limit: int,
        after: datetime,
    ) -> ResponseListResponse:
        """Fetches a ResponseListResponse for a specific response_set_type. Results will be filtered according to the
        start/limit/after parameters and ordered according to sep2 Response ordering.

        Raises NotFoundError if the response_set_type is not supported"""
        if response_set_type == ResponseSetType.DYNAMIC_OPERATING_ENVELOPES:
            total_doe_responses = await count_doe_responses(session, scope.aggregator_id, scope.site_id, after)
            doe_responses = await select_doe_responses(
                session,
                aggregator_id=scope.aggregator_id,
                site_id=scope.site_id,
                start=start,
                limit=limit,
                created_after=after,
            )
            return ResponseListMapper.map_to_doe_response(scope, doe_responses, total_doe_responses)
        elif response_set_type == ResponseSetType.TARIFF_GENERATED_RATES:
            total_rate_responses = await count_tariff_generated_rate_responses(
                session, scope.aggregator_id, scope.site_id, after
            )
            rate_responses = await select_tariff_generated_rate_responses(
                session,
                aggregator_id=scope.aggregator_id,
                site_id=scope.site_id,
                start=start,
                limit=limit,
                created_after=after,
            )
            return ResponseListMapper.map_to_price_response(scope, rate_responses, total_rate_responses)
        else:
            raise NotFoundError(
                f"ResponseList for {response_set_type} either doesn't exist or is inaccessible in this scope"
            )
