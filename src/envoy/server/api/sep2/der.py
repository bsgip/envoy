import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.der import DERAvailability, DERCapability, DERSettings, DERStatus
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_default_doe,
    extract_limit_from_paging_param,
    extract_request_params,
    extract_start_from_paging_param,
)
from envoy.server.api.response import XmlRequest, XmlResponse
from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.der import (
    DERAvailabilityManager,
    DERCapabilityManager,
    DERManager,
    DERSettingsManager,
    DERStatusManager,
)
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.manager.derp import DERProgramManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head(uri.DERListUri)
@router.get(uri.DERListUri, status_code=HTTPStatus.OK)
async def get_der_list(
    request: Request,
    site_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> Response:
    """Responds with a single DERListResponse containing DER for the specified site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    try:
        der_list = await DERManager.fetch_der_list_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            start=extract_start_from_paging_param(start),
            limit=extract_limit_from_paging_param(limit),
            after=extract_datetime_from_paging_param(after),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(der_list)


@router.head(uri.DERUri)
@router.get(uri.DERUri, status_code=HTTPStatus.OK)
async def get_der(request: Request, site_id: int, der_id: int) -> Response:
    """Responds with a single DER for a site. This will always exist for a site.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to return
    Returns:
        fastapi.Response object.
    """
    try:
        der = await DERManager.fetch_der_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(der)


@router.head(uri.DERAvailabilityUri)
@router.get(uri.DERAvailabilityUri, status_code=HTTPStatus.OK)
async def get_der_availability(request: Request, site_id: int, der_id: int) -> Response:
    """Responds with the last DERAvailability submitted for a der. Returns 404 if none have been submitted

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        result = await DERAvailabilityManager.fetch_der_availability_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(result)


@router.put(uri.DERAvailabilityUri, status_code=HTTPStatus.NO_CONTENT)
async def put_der_availability(
    request: Request,
    site_id: int,
    der_id: int,
    payload: DERAvailability = Depends(XmlRequest(DERAvailability)),
) -> Response:
    """Updates/Creates the DERAvailability associated with a specific der. Returns HTTP 204 on success

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        await DERAvailabilityManager.upsert_der_availability_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
            der_availability=payload,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.head(uri.DERCapabilityUri)
@router.get(uri.DERCapabilityUri, status_code=HTTPStatus.OK)
async def get_der_capability(request: Request, site_id: int, der_id: int) -> Response:
    """Responds with the last DERCapability submitted for a der. Returns 404 if none have been submitted

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        result = await DERCapabilityManager.fetch_der_capability_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(result)


@router.put(uri.DERCapabilityUri, status_code=HTTPStatus.NO_CONTENT)
async def put_der_capability(
    request: Request,
    site_id: int,
    der_id: int,
    payload: DERCapability = Depends(XmlRequest(DERCapability)),
) -> Response:
    """Updates/Creates the DERCapability associated with a specific der. Returns HTTP 204 on success

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        await DERCapabilityManager.upsert_der_capability_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
            der_capability=payload,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.head(uri.DERStatusUri)
@router.get(uri.DERStatusUri, status_code=HTTPStatus.OK)
async def get_der_status(request: Request, site_id: int, der_id: int) -> Response:
    """Responds with the last DERStatus submitted for a der. Returns 404 if none have been submitted

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        result = await DERStatusManager.fetch_der_status_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(result)


@router.put(uri.DERStatusUri, status_code=HTTPStatus.NO_CONTENT)
async def put_der_status(
    request: Request,
    site_id: int,
    der_id: int,
    payload: DERStatus = Depends(XmlRequest(DERStatus)),
) -> Response:
    """Updates/Creates the DERStatus associated with a specific der. Returns HTTP 204 on success

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        await DERStatusManager.upsert_der_status_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
            der_status=payload,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.head(uri.DERSettingsUri)
@router.get(uri.DERSettingsUri, status_code=HTTPStatus.OK)
async def get_der_settings(request: Request, site_id: int, der_id: int) -> Response:
    """Responds with the last DERSettings submitted for a der. Returns 404 if none have been submitted

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        result = await DERSettingsManager.fetch_der_settings_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(result)


@router.put(uri.DERSettingsUri, status_code=HTTPStatus.NO_CONTENT)
async def put_der_settings(
    request: Request,
    site_id: int,
    der_id: int,
    payload: DERSettings = Depends(XmlRequest(DERSettings)),
) -> Response:
    """Updates/Creates the DERSettings associated with a specific der. Returns HTTP 204 on success

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        der_id: Path parameter, the target DER ID to fetch data for
    Returns:
        fastapi.Response object.
    """
    try:
        await DERSettingsManager.upsert_der_settings_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            site_der_id=der_id,
            der_settings=payload,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.head(uri.AssociatedDERProgramListUri)
@router.get(uri.AssociatedDERProgramListUri, status_code=HTTPStatus.OK)
async def get_derprogram_list(
    request: Request,
    site_id: int,
    der_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> Response:
    """Responds with a single DERProgramListResponse containing DER programs for the specified site/DER

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    if der_id != PUBLIC_SITE_DER_ID:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail=f"No DER with ID {der_id}")

    try:
        derp_list = await DERProgramManager.fetch_list_for_site(
            db.session,
            request_params=extract_request_params(request),
            site_id=site_id,
            default_doe=extract_default_doe(request),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derp_list)
