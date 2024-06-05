import logging
from datetime import datetime
from http import HTTPStatus

from envoy_schema.admin.schema.log import CalculationLogListResponse, CalculationLogRequest, CalculationLogResponse
from envoy_schema.admin.schema.uri import CalculationLogCreateUri, CalculationLogsForPeriod, CalculationLogUri
from fastapi import APIRouter, HTTPException, Path, Query, Response
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.log import CalculationLogManager
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param
from envoy.server.api.response import LOCATION_HEADER_NAME

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(CalculationLogsForPeriod, status_code=HTTPStatus.OK, response_model=CalculationLogListResponse)
async def get_calculation_log_for_period(
    period_start: datetime = Path(),
    period_end: datetime = Path(),
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
) -> CalculationLogListResponse:
    """Endpoint fetching a list of CalculationLogResponse instances that intersect a period.

    Path Params:
        period_start: The (inclusive) start datetime that defines the start of the period (include timezone)
        period_end: The (exclusive) end datetime that defines the end of the period (include timezone)

    Query Params:
        start: How many elements to skip in this page of results (defaults to 0)
        limit: How many elements to include in a single page (defaults to 100)

    Returns:
        CalculationLogListResponse

    """

    return await CalculationLogManager.get_calculation_logs_by_period(
        session=db.session,
        period_start=period_start,
        period_end=period_end,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
    )


@router.post(CalculationLogCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_calculation_log(calculation_log: CalculationLogRequest) -> Response:
    """Persists a new calculation_log. Returns the ID as a Location response header

    Body:
        single CalculationLogRequest object.

    Returns:
        None
    """
    log_id = await CalculationLogManager.save_calculation_log(db.session, calculation_log)
    location_href = CalculationLogUri.format(calculation_log_id=log_id)
    return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})


@router.get(CalculationLogUri, status_code=HTTPStatus.OK, response_model=CalculationLogResponse)
async def get_calculation_log_by_id(
    calculation_log_id: int,
) -> CalculationLogResponse:
    """Endpoint fetching a CalculationLogResponse for a known calculation log ID

    Returns:
        CalculationLogResponse

    """

    log = await CalculationLogManager.get_calculation_log_by_id(
        session=db.session,
        calculation_log_id=calculation_log_id,
    )

    if log is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Calculation log with ID {calculation_log_id} not found")

    return log
