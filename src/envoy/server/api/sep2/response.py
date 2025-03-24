import logging
from http import HTTPStatus
from typing import Union

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.response import DERControlResponse, PriceResponse
from envoy_schema.server.schema.sep2.response import Response as Sep2Response
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
from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.response import ResponseManager
from envoy.server.mapper.constants import ResponseSetType
from envoy.server.mapper.sep2.response import href_to_response_set_type

logger = logging.getLogger(__name__)

router = APIRouter()


def try_parse_response_set_type(site_id: int, response_list_id: str) -> ResponseSetType:
    """Parses the URI path component associated with a "response_list_id" into a ResponseSetType.

    raising a LoggedHttpException with appropriate HTTP status code if something doesn't work"""
    try:
        return href_to_response_set_type(response_list_id)
    except ValueError as exc:
        logger.error(
            f"ValueError: '{response_list_id}' does not map to a response set type for site {site_id}.", exc_info=exc
        )
        raise LoggedHttpException(
            logger, exc, status_code=HTTPStatus.NOT_FOUND, detail=f"ResponseSet '{response_list_id}' does not exist"
        )


@router.head(uri.ResponseSetUri)
@router.get(
    uri.ResponseSetUri,
    status_code=HTTPStatus.OK,
)
async def get_response_set(
    request: Request,
    site_id: int,
    response_list_id: str,
) -> XmlResponse:
    """Responds with a specific response set that exists underneath a site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        response_list_id: Path parameter, the "name" of the response set that the response exists under
        request: FastAPI request object.

    Returns:
        fastapi.Response object encoding a sep2 Response

    """

    response_set_type = try_parse_response_set_type(site_id, response_list_id)

    try:
        response = ResponseManager.fetch_response_set_for_scope(
            extract_request_claims(request).to_device_or_aggregator_request_scope(site_id),
            response_set_type=response_set_type,
        )
        return XmlResponse(response)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head(uri.ResponseSetListUri)
@router.get(
    uri.ResponseSetListUri,
    status_code=HTTPStatus.OK,
)
async def get_response_set_list(
    request: Request,
    site_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a list view of response sets that exist underneath a site (response sets contain ResponseList)

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        response_list_id: Path parameter, the "name" of the response list that the response exists under
        start: Query Parameter, the "start" or "skip" count. The number of respons set records to skip (for pagination)
        after: Query Parameter, Has no effect in this implementation
        limit: Query Parameter, the maximum number of response set records to be returned (for pagination)

        request: FastAPI request object.

    Returns:
        fastapi.Response object encoding a sep2 ResponseSetList

    """

    try:
        response = ResponseManager.fetch_response_set_list_for_scope(
            scope=extract_request_claims(request).to_device_or_aggregator_request_scope(site_id),
            start=extract_start_from_paging_param(start),
            limit=extract_limit_from_paging_param(limit),
        )
        return XmlResponse(response)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head(uri.ResponseUri)
@router.get(
    uri.ResponseUri,
    status_code=HTTPStatus.OK,
)
async def get_response(
    request: Request,
    site_id: int,
    response_list_id: str,
    response_id: int,
) -> XmlResponse:
    """Responds with a specific response that exists underneath a site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        response_list_id: Path parameter, the "name" of the response list that the response exists under
        response_id: Path parameter, the target response ID
        request: FastAPI request object.

    Returns:
        fastapi.Response object encoding a sep2 Response

    """

    response_set_type = try_parse_response_set_type(site_id, response_list_id)

    try:
        response = await ResponseManager.fetch_response_for_scope(
            db.session,
            extract_request_claims(request).to_device_or_aggregator_request_scope(site_id),
            response_set_type=response_set_type,
            response_id=response_id,
        )
        return XmlResponse(response)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head(uri.ResponseListUri)
@router.get(
    uri.ResponseListUri,
    status_code=HTTPStatus.OK,
)
async def get_response_list(
    request: Request,
    site_id: int,
    response_list_id: str,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a list view of responses that exist underneath a site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        response_list_id: Path parameter, the "name" of the response list that the response exists under
        start: Query Parameter, the "start" or "skip" count. The number of response records to skip (for pagination)
        after: Query Parameter, Only responses created on/after this time will be included in the list
        limit: Query Parameter, the maximum number of response records to be returned (for pagination)

        request: FastAPI request object.

    Returns:
        fastapi.Response object encoding a sep2 ResponseList

    """

    response_set_type = try_parse_response_set_type(site_id, response_list_id)

    try:
        response = await ResponseManager.fetch_response_list_for_scope(
            db.session,
            extract_request_claims(request).to_device_or_aggregator_request_scope(site_id),
            response_set_type=response_set_type,
            start=extract_start_from_paging_param(start),
            after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
        return XmlResponse(response)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.post(uri.ResponseListUri, status_code=HTTPStatus.CREATED)
async def create_response(
    request: Request,
    site_id: int,
    response_list_id: str,
    payload: Union[DERControlResponse, PriceResponse, Sep2Response] = Depends(
        XmlRequest(DERControlResponse, PriceResponse, Sep2Response)
    ),
) -> Response:
    """Creates a "Response" to an existing TimeTariffInterval or DERControl.

    Returns a BadRequest if the incoming subject is malformed or doesn't reference a DERControl / TimeTariffInterval
    associated with site_id

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        response_list_id: Path parameter, the "name" of the response list that the response will be created under
        payload: The request payload/body object of the sep2 Response. Type will depend on response_list_id

    Returns:
        fastapi.Response object with a LOCATION_HEADER_NAME header with the href of the newly created response.

    """
    response_set_type = try_parse_response_set_type(site_id, response_list_id)

    try:
        location_href = await ResponseManager.create_response_for_scope(
            db.session,
            scope=extract_request_claims(request).to_device_or_aggregator_request_scope(site_id),
            response_set_type=response_set_type,
            response=payload,
        )

        return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})
    except BadRequestError as exc:
        raise LoggedHttpException(logger, exc, detail=exc.message, status_code=HTTPStatus.BAD_REQUEST)
