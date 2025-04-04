from http import HTTPStatus

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from fastapi import APIRouter, Request
from fastapi_async_sqlalchemy import db

from envoy.server.api.request import extract_request_claims
from envoy.server.api.response import XmlResponse
from envoy.server.manager.device_capability import DeviceCapabilityManager

router = APIRouter(tags=["device capability"])


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
    device_capability = await DeviceCapabilityManager.fetch_device_capability(
        session=db.session, scope=extract_request_claims(request).to_unregistered_request_scope()
    )
    return XmlResponse(device_capability)
