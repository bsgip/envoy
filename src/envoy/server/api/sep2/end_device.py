import logging
from http import HTTPStatus

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.sep2.end_device import EndDeviceRequest
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_request_params,
    extract_start_from_paging_param,
)
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.exception import BadRequestError
from envoy.server.manager.end_device import EndDeviceListManager, EndDeviceManager
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
    end_device = await EndDeviceManager.fetch_enddevice_with_site_id(
        db.session, site_id, extract_request_params(request)
    )
    if end_device is None:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(end_device)


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
        await EndDeviceListManager.fetch_enddevicelist_with_aggregator_id(
            db.session,
            extract_request_params(request),
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
    rs_params = extract_request_params(request)
    try:
        site_id = await EndDeviceManager.add_or_update_enddevice_for_aggregator(db.session, rs_params, payload)
        location_href = generate_href(uri.EndDeviceUri, rs_params, site_id=site_id)
        return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})
    except BadRequestError as exc:
        raise LoggedHttpException(logger, exc, detail=exc.message, status_code=HTTPStatus.BAD_REQUEST)
    except IntegrityError as exc:
        raise LoggedHttpException(logger, exc, detail="lFDI conflict.", status_code=HTTPStatus.CONFLICT)
