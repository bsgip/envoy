import logging
from datetime import datetime
from http import HTTPStatus
from envoy_schema.admin.schema.site_reading import AdminSiteReadingPageResponse
from fastapi import APIRouter, Query
from fastapi_async_sqlalchemy import db
from envoy_schema.admin.schema.uri import SiteReadingUri
from envoy.admin.manager.site_reading import AdminSiteReadingManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(SiteReadingUri, status_code=HTTPStatus.OK, response_model=AdminSiteReadingPageResponse)
async def get_site_readings(
    site_id: int,
    period_start: datetime,
    period_end: datetime,
    start: int = Query(0),
    limit: int = Query(1000),
) -> AdminSiteReadingPageResponse:
    """Endpoint for a paginated list of AdminSiteReading objects.

    Path Params:
        site_id: site_id for which to obtain readings
        period_start: earliest time range of readings
        period_end: latest time range of readings

    Query Params:
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 1000.

    Returns:
        AdminSiteReadingPageResponse
    """
    return await AdminSiteReadingManager.get_site_readings_for_site_and_time(
        session=db.session,
        site_id=site_id,
        start_time=period_start,
        end_time=period_end,
        start=start,
        limit=limit,
    )
