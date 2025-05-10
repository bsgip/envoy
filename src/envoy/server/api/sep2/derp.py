import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from fastapi import APIRouter, Query, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_default_doe,
    extract_limit_from_paging_param,
    extract_request_claims,
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
        derp_list = await DERProgramManager.fetch_list_for_scope(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            default_doe=extract_default_doe(request),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

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
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"DERProgram {der_program_id} Not found")

    try:
        derp = await DERProgramManager.fetch_doe_program_for_scope(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            default_doe=extract_default_doe(request),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

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
    """Responds with a single DERControlListResponse containing, non expired (according to server time), DER Controls
    for the specified site under the dynamic operating envelope program.

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
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"DERProgram {der_program_id} Not found")

    try:
        derc_list = await DERControlManager.fetch_doe_controls_for_scope(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derc_list)


@router.head(uri.ActiveDERControlListUri)
@router.get(uri.ActiveDERControlListUri, status_code=HTTPStatus.OK)
async def get_active_dercontrol_list(
    request: Request,
    site_id: int,
    der_program_id: str,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> Response:
    """Responds with a single DERControlListResponse containing DER Controls for the specified site under the
    dynamic operating envelope program. Only currently active (according to server time) controls will be returned.

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
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"DERProgram {der_program_id} Not found")

    try:
        derc_list = await DERControlManager.fetch_active_doe_controls_for_scope(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derc_list)


@router.head(uri.DefaultDERControlUri)
@router.get(uri.DefaultDERControlUri, status_code=HTTPStatus.OK)
async def get_default_dercontrol(
    request: Request,
    site_id: int,
    der_program_id: str,
) -> Response:
    """Responds with a single DefaultDERControl containing the default DER Controls for the specified site under the
    dynamic operating envelope program. Returns 404 if no default has been configured

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
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"DERProgram {der_program_id} Not found")

    try:
        derc_list = await DERControlManager.fetch_default_doe_controls_for_site(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            default_doe=extract_default_doe(request),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derc_list)


@router.head(uri.DERControlAndListByDateUri)
@router.get(uri.DERControlAndListByDateUri, status_code=HTTPStatus.OK)
async def get_dercontrol_by_id(
    request: Request,
    site_id: int,
    der_program_id: str,
    derc_id_or_date: int,  # The name is a reference to some deprecated functionality. It's just a derc_id now
) -> Response:
    """Fetches a DERControl by its id.

    Responds with a single DERControlResponse with the specified ID or with 404 if it does not exist or is inaccessible

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_program_id: DERProgramID - only 'doe' is supported
        derc_id_or_date: Path parameter, ID of the DERControl to return.

    Returns:
        fastapi.Response object.
    """
    if der_program_id != DOE_PROGRAM_ID:
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"DERProgram {der_program_id} Not found")

    try:
        derc = await DERControlManager.fetch_doe_control_for_scope(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            doe_id=derc_id_or_date,
        )

        if derc is None:
            raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

        return XmlResponse(derc)
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
