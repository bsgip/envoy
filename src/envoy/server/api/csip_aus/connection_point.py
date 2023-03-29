import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import NoResultFound

from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.manager.end_device import EndDeviceManager
from envoy.server.schema.csip_aus.connection_point import ConnectionPointRequest

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head("/edev/{site_id}/cp")
@router.get("/edev/{site_id}/cp", status_code=HTTPStatus.OK)
async def get_connectionpoint(site_id: int, request: Request):
    """Responds with a single ConnectionPointResponse resource linked to the EndDevice (as per CSIP-Aus).

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        connection_point = await EndDeviceManager.fetch_connection_point_for_site(
            db.session, site_id, request.state.aggregator_id
        )
        if connection_point is None:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")

    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(connection_point)


@router.put("/edev/{site_id}/cp", status_code=HTTPStatus.CREATED)
@router.post("/edev/{site_id}/cp", status_code=HTTPStatus.CREATED)
async def update_connectionpoint(
    site_id: int,
    request: Request,
    payload: ConnectionPointRequest = Depends(XmlRequest(ConnectionPointRequest)),
):
    """Updates the connection point details associated with an EndDevice resource.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        payload: The request payload/body object.

    Returns:
        fastapi.Response object.

    """
    updated = await EndDeviceManager.update_nmi_for_site(
        db.session, request.state.aggregator_id, site_id, payload.id
    )
    if not updated:
        return Response(status_code=HTTPStatus.NOT_FOUND)

    return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: f"/edev/{site_id}/cp"})