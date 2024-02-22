import logging
from http import HTTPStatus
from typing import Optional

from envoy_schema.admin.schema.site import SitePageResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse
from envoy_schema.admin.schema.uri import SiteGroupListUri, SiteGroupUri, SiteUri
from fastapi import APIRouter, HTTPException, Query
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.site import SiteManager
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(SiteUri, status_code=HTTPStatus.OK, response_model=SitePageResponse)
async def get_all_sites(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
    group: list[str] = Query([]),
) -> SitePageResponse:
    """Endpoint for a paginated list of Site Objects, ordered by site_id attribute.

    Query Param:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 100.
        group: list query parameter for the SiteGroup name by which to filter returned sites. Default no filter

    Returns:
        SitePageResponse

    """
    group_filter: Optional[str] = None
    if group is not None and len(group) > 0:
        group_filter = group[0]

    return await SiteManager.get_all_sites(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        group_filter=group_filter,
    )


@router.get(SiteGroupListUri, status_code=HTTPStatus.OK, response_model=SiteGroupPageResponse)
async def get_all_groups(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
) -> SiteGroupPageResponse:
    """Endpoint for a paginated list of SiteGroup Objects, ordered by site_group_id attribute.

    Query Param:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 100.

    Returns:
        SiteGroupPageResponse

    """

    return await SiteManager.get_all_site_groups(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
    )


@router.get(SiteGroupUri, status_code=HTTPStatus.OK, response_model=SiteGroupResponse)
async def get_group(
    group_name: str,
) -> SiteGroupResponse:
    """Endpoint for requesting a SiteGroup instance by its unique name,

    Returns:
        SiteGroupResponse

    """
    if not group_name:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "No group_name specified on path")

    grp = await SiteManager.get_all_site_group_by_name(session=db.session, group_name=group_name)
    if grp is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Group with name '{group_name}' not found")
    return grp
