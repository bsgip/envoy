import logging
from datetime import datetime
from http import HTTPStatus

from envoy_schema.admin.schema.log import CalculationLogRequest, CalculationLogResponse
from envoy_schema.admin.schema.uri import CalculationLogCreateUri, CalculationLogForDateUri, CalculationLogUri
from fastapi import APIRouter, HTTPException, Response
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.log import CalculationLogManager
from envoy.server.api.response import LOCATION_HEADER_NAME

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get(CalculationLogForDateUri, status_code=HTTPStatus.OK, response_model=CalculationLogResponse)
async def get_calculation_log_by_interval_start(
    calculation_interval_start: datetime,
) -> CalculationLogResponse:
    """Endpoint fetching a CalculationLogResponse for a known calculation log ID

    Returns:
        CalculationLogResponse

    """

    log = await CalculationLogManager.get_calculation_log_by_interval_start(
        session=db.session,
        interval_start=calculation_interval_start,
    )

    if log is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Calculation log with interval start {calculation_interval_start.isoformat()} not found",
        )

    return log
