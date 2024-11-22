import logging
from http import HTTPStatus
from typing import Union

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.metering_mirror import (
    MirrorMeterReadingListRequest,
    MirrorMeterReadingRequest,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
    MirrorUsagePointRequest,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_request_claims,
    extract_start_from_paging_param,
)
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.exception import BadRequestError, ForbiddenError, NotFoundError
from envoy.server.manager.metering import MirrorMeteringManager
from envoy.server.mapper.common import generate_href

router = APIRouter(tags=["metering mirror"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# GET /mup
@router.head(uri.MirrorUsagePointListUri)
@router.get(
    uri.MirrorUsagePointListUri,
    response_class=XmlResponse,
    response_model=MirrorUsagePointListResponse,
    status_code=HTTPStatus.OK,
)
async def get_mirror_usage_point_list(
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of mirror usage points available to the current client.

    Args:
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        mup_list = await MirrorMeteringManager.list_mirror_usage_points(
            db.session,
            scope=extract_request_claims(request).to_mup_request_scope(),
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except ForbiddenError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.FORBIDDEN, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(mup_list)


# POST /mup
@router.post(
    uri.MirrorUsagePointListUri,
    status_code=HTTPStatus.CREATED,
)
async def post_mirror_usage_point_list(
    request: Request,
    payload: MirrorUsagePointRequest = Depends(XmlRequest(MirrorUsagePointRequest)),
) -> Response:
    """Creates a mirror usage point for the current client. If the mup aligns with an existing mup for the specified
    site / aggregator then that will be returned instead

    Returns:
        fastapi.Response object.

    """
    scope = extract_request_claims(request).to_mup_request_scope()
    try:
        mup_id = await MirrorMeteringManager.create_or_update_mirror_usage_point(db.session, scope=scope, mup=payload)
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except ForbiddenError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.FORBIDDEN, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(
        status_code=HTTPStatus.CREATED,
        headers={LOCATION_HEADER_NAME: generate_href(uri.MirrorUsagePointUri, scope, mup_id=mup_id)},
    )


# GET /mup/{mup_id}
@router.head(uri.MirrorUsagePointUri)
@router.get(
    uri.MirrorUsagePointUri,
    response_class=XmlResponse,
    response_model=MirrorUsagePoint,
    status_code=HTTPStatus.OK,
)
async def get_mirror_usage_point(
    request: Request,
    mup_id: int,
) -> XmlResponse:
    """Responds with a MirrorUsagePoint for the specified mup_id (if the client can access the mup)
    or returns a HTTP 404 otherwise.

    Args:
        mup_id: The MirrorUsagePoint id to request

    Returns:
        fastapi.Response object.
    """
    try:
        mup_list = await MirrorMeteringManager.fetch_mirror_usage_point(
            db.session,
            scope=extract_request_claims(request).to_mup_request_scope(),
            site_reading_type_id=mup_id,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except ForbiddenError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.FORBIDDEN, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(mup_list)


# DELETE /mup/{mup_id}
@router.delete(
    uri.MirrorUsagePointUri,
    status_code=HTTPStatus.NO_CONTENT,
)
async def delete_mirror_usage_point(
    request: Request,
    mup_id: int,
) -> Response:
    """Deletes the specified MUP resource. The delete will also delete all linked readings. While data will be archived,
    it will remain inaccessible to the client via the csip-aus API.

    Will return 404 if the MUP doesn't exist / inaccessible, otherwise a 204 will be returned on success

    Args:
        mup_id: The MirrorUsagePoint id to delete

    Returns:
        fastapi.Response object.
    """
    removed = await MirrorMeteringManager.delete_mirror_usage_point(
        db.session,
        scope=extract_request_claims(request).to_mup_request_scope(),
        site_reading_type_id=mup_id,
    )
    return Response(status_code=HTTPStatus.NO_CONTENT if removed else HTTPStatus.NOT_FOUND)


# POST /mup/{mup_id}
@router.post(uri.MirrorUsagePointUri, status_code=HTTPStatus.CREATED)
async def post_mirror_usage_point(
    request: Request,
    mup_id: int,
    payload: Union[MirrorMeterReadingRequest, MirrorMeterReadingListRequest] = Depends(
        XmlRequest(MirrorMeterReadingRequest, MirrorMeterReadingListRequest)
    ),
) -> Response:
    """Allows the submission of readings for a particular MirrorUsagePoint with a specified mup_id. Returns HTTP 201 on
    success or a HTTP 404 if the client doesn't have access to this MirrorUsagePoint

    Args:
        mup_id: The MirrorUsagePoint id to submit readings for

    Returns:
        fastapi.Response object.
    """

    # we dont support sending a list mmr for now
    if isinstance(payload, MirrorMeterReadingListRequest):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Request body must be a MirrorMeterReading")

    try:
        await MirrorMeteringManager.add_or_update_readings(
            db.session,
            scope=extract_request_claims(request).to_mup_request_scope(),
            site_reading_type_id=mup_id,
            mmr=payload,
        )
    except BadRequestError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except ForbiddenError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.FORBIDDEN, detail=ex.message)
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(status_code=HTTPStatus.CREATED)
