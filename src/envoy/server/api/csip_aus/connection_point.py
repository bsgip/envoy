import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointRequest
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.request import extract_request_params
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.manager.end_device import EndDeviceManager
from envoy.server.mapper.common import generate_href

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head(uri.ConnectionPointUri)
@router.get(uri.ConnectionPointUri, status_code=HTTPStatus.OK)
async def get_connectionpoint(site_id: int, request: Request) -> Response:
    """Responds with a single ConnectionPointResponse resource linked to the EndDevice (as per CSIP-Aus).

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    connection_point = await EndDeviceManager.fetch_connection_point_for_site(
        db.session, site_id, extract_request_params(request)
    )
    if connection_point is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(connection_point)


@router.put(uri.ConnectionPointUri, status_code=HTTPStatus.CREATED)
@router.post(uri.ConnectionPointUri, status_code=HTTPStatus.CREATED)
async def update_connectionpoint(
    site_id: int,
    request: Request,
    payload: ConnectionPointRequest = Depends(XmlRequest(ConnectionPointRequest)),
) -> Response:
    """Updates the connection point details associated with an EndDevice resource.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        payload: The request payload/body object.

    Returns:
        fastapi.Response object.

    """
    rs_params = extract_request_params(request)
    updated = await EndDeviceManager.update_nmi_for_site(db.session, rs_params, site_id, payload.id)
    if not updated:
        return Response(status_code=HTTPStatus.NOT_FOUND)

    location_href = generate_href(uri.ConnectionPointUri, rs_params, site_id=site_id)
    return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})
