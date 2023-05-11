from http import HTTPStatus

from fastapi import APIRouter, Depends, Request

# from envoy.server.api.request import extract_aggregator_id
from envoy.server.api.response import XmlRequest, XmlResponse
from envoy.server.schema import uri
from envoy.server.schema.sep2.metering_mirror import MirrorUsagePointListResponse, MirrorUsagePointRequest

# from fastapi_async_sqlalchemy import db


router = APIRouter(tags=["metering mirror"])


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
    payload: MirrorUsagePointRequest = Depends(XmlRequest(MirrorUsagePointRequest)),
) -> XmlResponse:
    pass


# /mup/{mup_id}
# @router.put  # payload= MirrorUsagePoint
# @router.post  # payload= MirrorMeterReading
# @router.post  # payload= MirrorMeterReadingList
# @router.delete
