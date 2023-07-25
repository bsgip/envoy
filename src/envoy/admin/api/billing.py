import logging
from datetime import datetime
from http import HTTPStatus

from envoy_schema.admin.schema.billing import BillingResponse
from envoy_schema.admin.schema.uri import BillingUri
from fastapi import APIRouter, HTTPException, Path
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.billing import BillingManager
from envoy.server.exception import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(BillingUri, status_code=HTTPStatus.OK, response_model=BillingResponse)
async def get_billing_data(
    aggregator_id: int = Path(),
    tariff_id: int = Path(),
    period_start: datetime = Path(),
    period_end: datetime = Path(),
) -> BillingResponse:
    """Endpoint for fetching all aggregator billing data associated with a time period. This is a relatively intensive
    operation - it's been designed for running over a daily period.

    Query Param:
        period_start: The (inclusive) start datetime to request data for (include timezone)
        period_end: The (exclusive) end datetime to request data for (include timezone)
        aggregator_id: The aggregator id to request data for
        tariff_id: The tariff id to request rate data for

    Returns:
        BillingResponse

    """
    try:
        return await BillingManager.generate_billing_report(
            session=db.session,
            aggregator_id=aggregator_id,
            tariff_id=tariff_id,
            period_start=period_start,
            period_end=period_end,
        )
    except NotFoundError as exc:
        logger.debug(exc)
        raise HTTPException(detail="The requested aggregator id doesn't exist", status_code=HTTPStatus.NOT_FOUND)
