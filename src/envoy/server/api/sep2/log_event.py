import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.log_events import LogEvent
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
from envoy.server.exception import NotFoundError
from envoy.server.manager.log_event import LogEventManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head(uri.LogEventUri)
@router.get(
    uri.LogEventUri,
    status_code=HTTPStatus.OK,
)
async def get_log_event(
    request: Request,
    site_id: int,
    log_event_id: int,
) -> XmlResponse:
    """Responds with a specific LogEvent that exists underneath a site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        log_event_id: Path parameter, the target log event ID
        request: FastAPI request object.

    Returns:
        fastapi.Response object encoding a sep2 LogEvent

    """

    try:
        response = await LogEventManager.fetch_log_event_for_scope(
            db.session,
            extract_request_claims(request).to_device_or_aggregator_request_scope(site_id),
            log_event_id=log_event_id,
        )
        return XmlResponse(response)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head(uri.LogEventListUri)
@router.get(
    uri.LogEventListUri,
    status_code=HTTPStatus.OK,
)
async def get_log_event_list(
    request: Request,
    site_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a list view of LogEvents that exist underneath a site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        start: Query Parameter, the "start" or "skip" count. The number of response records to skip (for pagination)
        after: Query Parameter, Only responses created on/after this time will be included in the list
        limit: Query Parameter, the maximum number of response records to be returned (for pagination)

        request: FastAPI request object.

    Returns:
        fastapi.Response object encoding a sep2 LogEventList

    """

    try:
        response = await LogEventManager.fetch_log_event_list_for_scope(
            db.session,
            extract_request_claims(request).to_device_or_aggregator_request_scope(site_id),
            start=extract_start_from_paging_param(start),
            after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
        return XmlResponse(response)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.post(uri.LogEventListUri, status_code=HTTPStatus.CREATED)
async def create_log_event(
    request: Request,
    site_id: int,
    payload: LogEvent = Depends(XmlRequest(LogEvent)),
) -> Response:
    """Creates a "LogEvent" underneath the specified site id.

    Can return 404 if the site_id isn't accessible to the client

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        payload: The request payload/body object of the sep2 LogEvent to persist.

    Returns:
        fastapi.Response object with a LOCATION_HEADER_NAME header with the href of the newly created LogEvent.

    """

    try:
        location_href = await LogEventManager.create_log_event_for_scope(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            log_event=payload,
        )

        return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, detail=exc.message, status_code=HTTPStatus.NOT_FOUND)
