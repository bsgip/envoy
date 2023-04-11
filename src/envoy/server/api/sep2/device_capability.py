import logging
from http import HTTPStatus

from fastapi import APIRouter, Request

from envoy.server.api.response import XmlResponse
from envoy.server.manager.device_capability import DeviceCapabilityManager
from envoy.server.schema.sep2 import uri
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse

router = APIRouter(tags=["device capability"])

logger = logging.getLogger(__name__)


# /dcap
@router.head(uri.DeviceCapabilityUri)
@router.get(
    uri.DeviceCapabilityUri,
    response_class=XmlResponse,
    response_model=DeviceCapabilityResponse,
    status_code=HTTPStatus.OK,
)
async def device_capability(request: Request) -> XmlResponse:
    """Responds with the DeviceCapability resource.
    Args:
        request: FastAPI request object.
    Returns:
        fastapi.Response object.
    """
    # logger.info("Handling device capability request")
    # dcap_dict = {"href": request.url.path, "pollrate": 900}
    # dcap = DeviceCapabilityResponse(**dcap_dict)
    device_capability = await DeviceCapabilityManager.fetch_device_capability()
    return XmlResponse(device_capability)
