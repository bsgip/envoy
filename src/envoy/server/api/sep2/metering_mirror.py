import logging
from http import HTTPStatus
from typing import Annotated, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.request import (
    extract_aggregator_id,
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_start_from_paging_param,
)

# from envoy.server.api.request import extract_aggregator_id
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.metering import MirrorMeteringManager
from envoy.server.schema import uri
from envoy.server.schema.sep2.metering_mirror import (
    MirrorMeterReadingListRequest,
    MirrorMeterReadingRequest,
    MirrorUsagePointListResponse,
    MirrorUsagePointRequest,
)

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
            aggregator_id=extract_aggregator_id(request),
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

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
    try:
        mup_id = await MirrorMeteringManager.create_or_fetch_mirror_usage_point(
            db.session, aggregator_id=extract_aggregator_id(request), mup=payload
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(
        status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: uri.MirrorUsagePointUri.format(mup_id=mup_id)}
    )


# PUT /mup
@router.put(uri.MirrorUsagePointListUri, status_code=HTTPStatus.OK)
async def put_mirror_usage_point(
    request: Request,
    payload: Annotated[MirrorUsagePointRequest, Depends(XmlRequest(MirrorUsagePointRequest))],
) -> Response:
    """Creates/Updates a mirror usage point for the current client. If the mup aligns with an existing mup for the
    specified site / aggregator then that will be returned instead

    Returns:
        fastapi.Response object.

    """
    try:
        mup_id = await MirrorMeteringManager.create_or_fetch_mirror_usage_point(
            db.session, aggregator_id=extract_aggregator_id(request), mup=payload
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(
        status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: uri.MirrorUsagePointUri.format(mup_id=mup_id)}
    )


# POST /mup/{mup_id}
@router.post(uri.MirrorUsagePointUri, status_code=HTTPStatus.CREATED)
async def post_mirror_usage_point(
    request: Request,
    mup_id: int,
    payload: Union[MirrorMeterReadingRequest, MirrorMeterReadingListRequest] = Depends(
        XmlRequest(MirrorMeterReadingRequest, MirrorMeterReadingListRequest)
    ),
) -> Response:
    # we dont support sending a list mmr for now
    if isinstance(payload, MirrorMeterReadingListRequest):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Request body must be a MirrorMeterReading")

    try:
        mup_id = await MirrorMeteringManager.add_or_update_readings(
            db.session, aggregator_id=extract_aggregator_id(request), site_reading_type_id=mup_id, mmr=payload
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError as ex:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return Response(status_code=HTTPStatus.CREATED)


# DELETE /mup/{mup_id}
@router.delete(uri.MirrorUsagePointUri, status_code=HTTPStatus.OK)
async def delete_mirror_usage_point(request: Request) -> Response:
    return Response(status_code=HTTPStatus.OK)
