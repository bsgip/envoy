import logging
from http import HTTPStatus
from typing import Annotated, Union

from fastapi import APIRouter, Depends, Request, Response

# from envoy.server.api.request import extract_aggregator_id
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
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
async def get_mirror_usage_point_list(request: Request) -> XmlResponse:
    return XmlResponse(MirrorUsagePointListResponse())


# POST /mup
@router.post(
    uri.MirrorUsagePointListUri,
    status_code=HTTPStatus.CREATED,
)
async def post_mirror_usage_point_list(
    request: Request,
    payload: Annotated[MirrorUsagePointRequest, Depends(XmlRequest(MirrorUsagePointRequest))],
) -> Response:
    # Create the MUP

    # Here are are temporarily hard-coding the "created" MUP id.
    mup_id = 1
    return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: f"/mup/{mup_id}"})


# PUT /mup/{mup_id}
@router.put(uri.MirrorUsagePointUri, status_code=HTTPStatus.OK)
async def put_mirror_usage_point(
    request: Request,
    payload: Annotated[MirrorUsagePointRequest, Depends(XmlRequest(MirrorUsagePointRequest))],
) -> Response:
    # This should probably only allow updating and not creation of new Mirror Usage Points since we
    # don't want clients choosing their own ids
    return Response(status_code=HTTPStatus.CREATED)


# POST /mup/{mup_id}
@router.post(uri.MirrorUsagePointUri, status_code=HTTPStatus.CREATED)
async def post_mirror_usage_point(
    request: Request,
    payload: Annotated[
        Union[MirrorMeterReadingRequest, MirrorMeterReadingListRequest],
        Depends(XmlRequest(MirrorMeterReadingRequest, MirrorMeterReadingListRequest)),
    ],
) -> Response:
    return Response(status_code=HTTPStatus.CREATED)


# DELETE /mup/{mup_id}
@router.delete(uri.MirrorUsagePointUri, status_code=HTTPStatus.OK)
async def delete_mirror_usage_point(request: Request) -> Response:
    return Response(status_code=HTTPStatus.OK)
