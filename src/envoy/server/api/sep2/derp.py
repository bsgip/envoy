import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.request import (
    extract_date_from_iso_string,
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_request_params,
    extract_start_from_paging_param,
)
from envoy.server.api.response import XmlResponse
from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.derp import DERControlManager, DERProgramManager
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head(uri.DERProgramListUri)
@router.get(uri.DERProgramListUri, status_code=HTTPStatus.OK)
async def get_derprogram_list(
    request: Request,
    site_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> Response:
    """Responds with a single DERProgramListResponse containing DER programs for the specified site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    try:
        derp_list = await DERProgramManager.fetch_list_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derp_list)


@router.head(uri.DERProgramUri)
@router.get(uri.DERProgramUri, status_code=HTTPStatus.OK)
async def get_derprogram_doe(request: Request, site_id: int, der_program_id: str) -> Response:
    """Responds with a single DERProgramResponse for the DER Program specific to dynamic operating envelopes

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_program_id: DERProgramID - only 'doe' is supported
    Returns:
        fastapi.Response object.
    """
    if der_program_id != DOE_PROGRAM_ID:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    try:
        derp = await DERProgramManager.fetch_doe_program_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derp)


@router.head(uri.DERControlListUri)
@router.get(uri.DERControlListUri, status_code=HTTPStatus.OK)
async def get_dercontrol_list(
    request: Request,
    site_id: int,
    der_program_id: str,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> Response:
    """Responds with a single DERControlListResponse containing DER Controls for the specified site under the
    dynamic operating envelope program.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_program_id: DERProgramID - only 'doe' is supported
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    if der_program_id != DOE_PROGRAM_ID:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    try:
        derc_list = await DERControlManager.fetch_doe_controls_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derc_list)


@router.head(uri.DERControlListByDateUri)
@router.get(uri.DERControlListByDateUri, status_code=HTTPStatus.OK)
async def get_dercontrol_list_for_date(
    request: Request,
    site_id: int,
    der_program_id: str,
    date: str,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> Response:
    """Responds with a single DERControlListResponse containing DER Controls for the specified site under the
    dynamic operating envelope program. Results will be filtered to the specified date

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_program_id: DERProgramID - only 'doe' is supported
        date: Path parameter, the YYYY-MM-DD in site local time that controls will be filtered to
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    if der_program_id != DOE_PROGRAM_ID:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    day = extract_date_from_iso_string(date)
    if day is None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Expected YYYY-MM-DD date")

    try:
        derc_list = await DERControlManager.fetch_doe_controls_for_site_day(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            day=day,
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derc_list)
