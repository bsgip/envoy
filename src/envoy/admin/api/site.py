import logging
from http import HTTPStatus

from envoy_schema.admin.schema.site import SitePageResponse
from envoy_schema.admin.schema.uri import SiteUri
from fastapi import APIRouter, Query
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.site import SiteManager
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(SiteUri, status_code=HTTPStatus.OK, response_model=SitePageResponse)
async def get_all_sites(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
) -> SitePageResponse:
    """Endpoint for a paginated list of Site Objects, ordered by site_id attribute.

    Query Param:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 100.

    Returns:
        SitePageResponse

    """

    return await SiteManager.get_all_sites(
        session=db.session, start=extract_start_from_paging_param(start), limit=extract_limit_from_paging_param(limit)
    )
