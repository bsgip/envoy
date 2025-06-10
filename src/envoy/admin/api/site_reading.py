import logging
from datetime import datetime
from http import HTTPStatus
from typing import Optional

from asyncpg.exceptions import CardinalityViolationError  # type: ignore
from envoy_schema.admin.schema.site_control import (
    SiteControlGroupPageResponse,
    SiteControlGroupRequest,
    SiteControlGroupResponse,
    SiteControlPageResponse,
    SiteControlRequest,
)
from envoy_schema.admin.schema.uri import SiteReadingUri
from fastapi import APIRouter, Query, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError

from envoy.admin.manager.site_reading import AdminSiteReadingManager
from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param
from envoy.server.api.response import LOCATION_HEADER_NAME

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(SiteReadingUri, status_code=HTTPStatus.OK, response_model=AdminSiteReadingManager)
async def get_site_reading(
    site_ids: list[int],
    start_time: datetime,
    end_time: datetime,
    start: int = Query(0),
    limit: int = Query(1000),
) -> SiteControlPageResponse:
    """Endpoint for a paginated list of AdminSiteReadingManager Objects, ordered by site_control_id
    attribute.

    Query Param:
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 100. Max 500.
        after: Filters objects that have been created/modified from this timestamp (inclusive). Default no filter.

    Returns:
        SiteControlPageResponse
    """
    return await AdminSiteReadingManager.get_all_site_controls(
        session=db.session,
        site_control_group_id=group_id,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        changed_after=after,
    )
