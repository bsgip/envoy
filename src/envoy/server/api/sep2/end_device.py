import logging
from http import HTTPStatus

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.sep2.end_device import EndDeviceRequest
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_request_claims,
    extract_start_from_paging_param,
)
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.exception import BadRequestError, ForbiddenError, NotFoundError, ConflictError
from envoy.server.manager.end_device import EndDeviceManager, RegistrationManager
from envoy.server.mapper.common import generate_href

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head(uri.EndDeviceUri)
@router.get(
    uri.EndDeviceUri,
    status_code=HTTPStatus.OK,
)
async def get_enddevice(site_id: int, request: Request) -> XmlResponse:
    """Responds with a single EndDevice resource.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    end_device = await EndDeviceManager.fetch_enddevice_for_scope(
        db.session, extract_request_claims(request).to_device_or_aggregator_request_scope(site_id)
    )
    if end_device is None:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(end_device)


@router.delete(
    uri.EndDeviceUri,
    status_code=HTTPStatus.NO_CONTENT,
)
async def delete_enddevice(site_id: int, request: Request) -> Response:
    """Deletes the specified EndDevice resource. The delete will also delete all linked subscriptions/mirror
    usage points. While data will be archived, it will remain inaccessible to the client via the csip-aus API.

    Will return 404 if the site doesn't exist / inaccessible, otherwise a 204 will be returned on success

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    removed = await EndDeviceManager.delete_enddevice_for_scope(
        db.session, extract_request_claims(request).to_site_request_scope(site_id)
    )
    return Response(status_code=HTTPStatus.NO_CONTENT if removed else HTTPStatus.NOT_FOUND)


@router.head(uri.EndDeviceListUri)
@router.get(
    uri.EndDeviceListUri,
    status_code=HTTPStatus.OK,
)
async def get_enddevice_list(
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a EndDeviceList resource.

    Args:
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """

    return XmlResponse(
        await EndDeviceManager.fetch_enddevicelist_for_scope(
            db.session,
            extract_request_claims(request).to_unregistered_request_scope(),
            start=extract_start_from_paging_param(start),
            after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    )


@router.post(uri.EndDeviceListUri, status_code=HTTPStatus.CREATED)
async def create_end_device(
    request: Request,
    payload: EndDeviceRequest = Depends(XmlRequest(EndDeviceRequest)),
) -> Response:
    """An EndDevice resource is generated with a unique reg_no (registration number).
    This reg_no is used to set the resource path i.e.'/edev/reg_no' which is
    sent to the client in the response 'Location' header.

    Args:
        response: fastapi.Response object.
        payload: The request payload/body object.

    Returns:
        fastapi.Response object.

    """
    scope = extract_request_claims(request).to_unregistered_request_scope()
    try:
        site_id = await EndDeviceManager.add_enddevice_for_scope(db.session, scope, payload)
        location_href = generate_href(uri.EndDeviceUri, scope, site_id=site_id)
        return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})
    except BadRequestError as exc:
        raise LoggedHttpException(logger, exc, detail=exc.message, status_code=HTTPStatus.BAD_REQUEST)
    except ForbiddenError as exc:
        raise LoggedHttpException(logger, exc, detail=exc.message, status_code=HTTPStatus.FORBIDDEN)
    except ConflictError as exc:
        raise LoggedHttpException(logger, exc, detail="lFDI or sFDI conflict.", status_code=HTTPStatus.CONFLICT)


@router.head(uri.RegistrationUri)
@router.get(
    uri.RegistrationUri,
    status_code=HTTPStatus.OK,
)
async def get_enddevice_registration(site_id: int, request: Request) -> XmlResponse:
    """Responds with a single Registration element for an EndDevice resource.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        end_device_registration = await RegistrationManager.fetch_registration_for_scope(
            db.session, extract_request_claims(request).to_site_request_scope(site_id)
        )
        return XmlResponse(end_device_registration)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail=exc.message)
