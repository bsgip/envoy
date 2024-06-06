import logging
from datetime import datetime
from http import HTTPStatus

from envoy_schema.admin.schema.billing import (
    AggregatorBillingResponse,
    CalculationLogBillingResponse,
    SiteBillingRequest,
    SiteBillingResponse,
)
from envoy_schema.admin.schema.uri import AggregatorBillingUri, CalculationLogBillingUri, SitePeriodBillingUri
from fastapi import APIRouter, Path
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.billing import BillingManager
from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.exception import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(AggregatorBillingUri, status_code=HTTPStatus.OK, response_model=AggregatorBillingResponse)
async def get_aggregator_billing_data(
    aggregator_id: int = Path(),
    tariff_id: int = Path(),
    period_start: datetime = Path(),
    period_end: datetime = Path(),
) -> AggregatorBillingResponse:
    """Endpoint for fetching all aggregator billing data associated with a time period. This is a relatively intensive
    operation - it's been designed for running over a daily period.

    Query Param:
        period_start: The (inclusive) start datetime to request data for (include timezone)
        period_end: The (exclusive) end datetime to request data for (include timezone)
        aggregator_id: The aggregator id to request data for
        tariff_id: The tariff id to request rate data for

    Returns:
        AggregatorBillingResponse

    """
    try:
        return await BillingManager.generate_aggregator_billing_report(
            session=db.session,
            aggregator_id=aggregator_id,
            tariff_id=tariff_id,
            period_start=period_start,
            period_end=period_end,
        )
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "The requested aggregator id doesn't exist")


@router.get(CalculationLogBillingUri, status_code=HTTPStatus.OK, response_model=CalculationLogBillingResponse)
async def get_calculation_log_billing_data(
    calculation_log_id: int = Path(),
    tariff_id: int = Path(),
) -> CalculationLogBillingResponse:
    """Endpoint for fetching all aggregator billing data associated with a time period. This is a relatively intensive
    operation - it's been designed for running over a daily period.

    Query Param:
        period_start: The (inclusive) start datetime to request data for (include timezone)
        period_end: The (exclusive) end datetime to request data for (include timezone)
        aggregator_id: The aggregator id to request data for
        tariff_id: The tariff id to request rate data for

    Returns:
        CalculationLogBillingResponse

    """
    try:
        return await BillingManager.generate_calculation_log_billing_report(
            session=db.session,
            calculation_log_id=calculation_log_id,
            tariff_id=tariff_id,
        )
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "The requested calculation log id doesn't exist")


@router.post(SitePeriodBillingUri, status_code=HTTPStatus.OK, response_model=SiteBillingResponse)
async def get_sites_billing_data(req: SiteBillingRequest) -> SiteBillingResponse:
    """Endpoint for fetching all site billing data associated with a time period. This is a relatively intensive
    operation - it's been designed for running over a daily period.

    POST Body SiteBillingRequest:
        period_start: The (inclusive) start datetime to request data for (include timezone)
        period_end: The (exclusive) end datetime to request data for (include timezone)
        site_ids: The site ids to request data for
        tariff_id: The tariff id to request rate data for

    Returns:
        SiteBillingResponse

    """
    return await BillingManager.generate_sites_billing_report(
        session=db.session,
        request=req,
    )
