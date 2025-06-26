import logging
from datetime import datetime
from http import HTTPStatus
from envoy_schema.admin.schema.site_reading import CSIPAusSiteReadingPageResponse, CSIPAusSiteReadingUnit
from envoy_schema.admin.schema.uri import CSIPAusSiteReadingUri
from fastapi import APIRouter, Query
from fastapi_async_sqlalchemy import db
from envoy.admin.manager.site_reading import AdminSiteReadingManager
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(CSIPAusSiteReadingUri, status_code=HTTPStatus.OK, response_model=CSIPAusSiteReadingPageResponse)
async def get_site_readings(
    site_id: int,
    unit_enum: CSIPAusSiteReadingUnit,
    period_start: datetime,
    period_end: datetime,
    start: list[int] = Query([0]),
    limit: list[int] = Query([500]),  # Max 500
) -> CSIPAusSiteReadingPageResponse:
    return await AdminSiteReadingManager.get_site_readings_for_site_and_time(
        session=db.session,
        site_id=site_id,
        csip_unit=unit_enum,
        start_time=period_start,
        end_time=period_end,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
    )
