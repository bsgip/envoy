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
from envoy_schema.admin.schema.uri import (
    SiteControlGroupListUri,
    SiteControlGroupUri,
    SiteControlRangeUri,
    SiteControlUri,
)
from fastapi import APIRouter, Query, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError

from envoy.admin.manager.site_control import SiteControlGroupManager, SiteControlListManager
from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param
from envoy.server.api.response import LOCATION_HEADER_NAME

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(SiteControlGroupListUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_site_control_group(site_control_group: SiteControlGroupRequest) -> Response:
    """Persists a new site control group. Returns the ID as a Location response header

    Body:
        single SiteControlGroupRequest object.

    Returns:
        None
    """
    site_control_group_id = await SiteControlGroupManager.create_site_control_group(db.session, site_control_group)
    location_href = SiteControlGroupUri.format(group_id=site_control_group_id)
    return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})


@router.get(SiteControlGroupUri, status_code=HTTPStatus.OK, response_model=SiteControlGroupResponse)
async def get_site_control_group(group_id: int) -> SiteControlGroupResponse:
    """Endpoint for fetching a single SiteControlGroupResponse by its ID

    Returns:
        SiteControlGroupResponse or 404 if it can't be found
    """
    result = await SiteControlGroupManager.get_site_control_group_by_id(
        session=db.session,
        site_control_group_id=group_id,
    )
    if result is None:
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"site_group_id {group_id} not found")
    return result


@router.get(SiteControlGroupListUri, status_code=HTTPStatus.OK, response_model=SiteControlGroupPageResponse)
async def get_all_site_control_groups(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
    after: Optional[datetime] = Query(None),
) -> SiteControlGroupPageResponse:
    """Endpoint for a paginated list of SiteControlGroupResponse Objects, ordered by the site_control_group_id
    attribute.

    Query Param:
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 100. Max 500.
        after: Filters objects that have been created/modified from this timestamp (inclusive). Default no filter.

    Returns:
        SiteControlGroupPageResponse
    """
    return await SiteControlGroupManager.get_all_site_control_groups(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        changed_after=after,
    )


@router.post(SiteControlUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_site_controls(group_id: int, control_list: list[SiteControlRequest]) -> None:
    """Bulk creation of 'Site Controls' under a site control group. Each SiteControlRequest is associated
    with a Site object via the site_id attribute.

    Body:
        List of SiteControlRequest objects.

    Returns:
        None
    """
    try:
        await SiteControlListManager.add_many_site_control(db.session, group_id, control_list)
    except CardinalityViolationError as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.BAD_REQUEST, "The request contains duplicate instances")
    except IntegrityError as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.BAD_REQUEST, "site_id not found")


@router.get(SiteControlUri, status_code=HTTPStatus.OK, response_model=SiteControlPageResponse)
async def get_all_site_controls(
    group_id: int,
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
    after: Optional[datetime] = Query(None),
) -> SiteControlPageResponse:
    """Endpoint for a paginated list of SiteControlResponse Objects, ordered by site_control_id
    attribute.

    Query Param:
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 100. Max 500.
        after: Filters objects that have been created/modified from this timestamp (inclusive). Default no filter.

    Returns:
        SiteControlPageResponse
    """
    return await SiteControlListManager.get_all_site_controls(
        session=db.session,
        site_control_group_id=group_id,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        changed_after=after,
    )


@router.delete(SiteControlRangeUri, status_code=HTTPStatus.NO_CONTENT, response_model=None)
async def delete_site_controls_in_range(group_id: int, period_start: datetime, period_end: datetime) -> None:
    """Deletes all DER controls for the specified group whose start time lies in the specified time range (inclusive
    start, exclusive end). All deleted controls will be properly cancelled / archived.

    Returns:
        None
    """

    await SiteControlListManager.delete_site_controls_in_range(
        db.session, site_control_group_id=group_id, site_id=None, period_start=period_start, period_end=period_end
    )
