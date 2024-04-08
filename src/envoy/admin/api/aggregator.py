import logging
from http import HTTPStatus

from envoy_schema.admin.schema.aggregator import AggregatorPageResponse, AggregatorResponse
from envoy_schema.admin.schema.uri import AggregatorListUri, AggregatorUri
from fastapi import APIRouter, HTTPException, Query
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.aggregator import AggregatorManager
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(AggregatorListUri, status_code=HTTPStatus.OK, response_model=AggregatorPageResponse)
async def get_all_aggregators(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
) -> AggregatorPageResponse:
    """Endpoint for a paginated list of Aggregator Objects, ordered by aggregator_id attribute.

    Query Param:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 100.

    Returns:
        AggregatorPageResponse

    """
    return await AggregatorManager.fetch_many_aggregators(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
    )


@router.get(AggregatorUri, status_code=HTTPStatus.OK, response_model=AggregatorResponse)
async def get_group(
    aggregator_id: int,
) -> AggregatorResponse:
    """Endpoint for requesting an Aggregator instance by its unique id,

    Returns:
        AggregatorResponse

    """

    agg = await AggregatorManager.fetch_single_aggregator(session=db.session, aggregator_id=aggregator_id)
    if agg is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Aggregator with ID {aggregator_id} not found")
    return agg
