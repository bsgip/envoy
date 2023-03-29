import logging

from fastapi import APIRouter, Request

from envoy.server.api.response import XmlResponse
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse

router = APIRouter(tags=["device capability"])

logger = logging.getLogger(__name__)


@router.head("/dcap")
@router.get(
    "/dcap",
    response_class=XmlResponse,
    response_model=DeviceCapabilityResponse,
    status_code=200,
)
async def device_capability(request: Request):
    logger.info("Handling device capability request")
    dcap_dict = {"href": request.url.path}
    dcap = DeviceCapabilityResponse(**dcap_dict)
    return XmlResponse(dcap)
