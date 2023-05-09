import logging
from http import HTTPStatus
from typing import Union

from fastapi import APIRouter, Depends, Request, Response

# from envoy.server.api.request import extract_aggregator_id
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.schema import uri
from envoy.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorMeterReadingList,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
    MirrorUsagePointRequest,
)

# from fastapi_async_sqlalchemy import db


router = APIRouter(tags=["metering mirror"])
logger = logging.getLogger("__name__")
logger.setLevel(logging.DEBUG)


# GET /mup
@router.head(uri.MirrorUsagePointListUri)
@router.get(
    uri.MirrorUsagePointListUri,
    response_class=XmlResponse,
    response_model=MirrorUsagePointListResponse,
    status_code=HTTPStatus.OK,
)
async def get_mirror_usage_point_list(request: Request) -> XmlResponse:
    return XmlResponse(MirrorUsagePointListResponse())


# POST /mup
@router.post(
    uri.MirrorUsagePointListUri,
    # response_class=XmlResponse,
    # response_model=MirrorUsagePointListResponse,
    status_code=HTTPStatus.CREATED,
)
async def post_mirror_usage_point_list(
    request: Request,
    payload: MirrorUsagePoint = Depends(XmlRequest(MirrorUsagePoint)),
) -> XmlResponse:
    logger.info(f"ENDPOINT 'post_mirror_usage_pointlist' with payload={payload}")
    mup_id = 1
    return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: f"/mup/{mup_id}"})


# PUT /mup/{mup_id}
@router.put(uri.MirrorUsagePointUri, status_code=HTTPStatus.OK)
async def put_mirror_usage_point(
    request: Request,
    payload: MirrorUsagePointRequest = Depends(XmlRequest(MirrorUsagePointRequest)),
) -> XmlResponse:
    # This should probably only all updating and not creation of new Mirror Usage Points since we
    # don't want clients choosing their own ids
    return Response(status_code=HTTPStatus.CREATED)


# POST /mup/{mup_id}
@router.post(uri.MirrorUsagePointUri, status_code=HTTPStatus.CREATED)
async def post_mirror_usage_point(
    request: Request,
    payload: Union[MirrorMeterReading, MirrorMeterReadingList],
) -> XmlResponse:
    return Response(status_code=HTTPStatus.CREATED)


# DELETE /mup/{mup_id}
@router.delete(uri.MirrorUsagePointUri, status_code=HTTPStatus.OK)
async def delete_mirror_usage_point(request: Request) -> XmlResponse:
    return Response(status_code=HTTPStatus.OK)
