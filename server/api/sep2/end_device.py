import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError, NoResultFound

from server.api.response import XmlRequest, XmlResponse
from server.manager.end_device import EndDeviceListManager, EndDeviceManager
from server.schema.sep2.end_device import (
    EndDeviceListResponse,
    EndDeviceRequest,
    EndDeviceResponse,
)

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head("/edev/{site_id}")
@router.get(
    "/edev/{site_id}",
    status_code=200,
)
async def get_enddevice(site_id: int, request: Request):
    """Responds with a single EndDevice resource.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        end_device = await EndDeviceManager.fetch_enddevice_with_site_id(
            db.session, site_id, request.state.aggregator_id
        )
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=404, detail="Not Found.")
    return XmlResponse(end_device)


@router.head("/edev")
@router.get(
    "/edev",
    status_code=200,
)
async def get_enddevice_list(
    request: Request,
    s: list[int] = Query([0]),
    a: list[int] = Query([0]),
    l: list[int] = Query([1]),
):
    """Responds with a EndDeviceList resource.

    Args:
        request: FastAPI request object.
        s: start, list query parameter for the start index value. Default 0.
        a: after, list query parameter for lists with a datetime primary index. Default 0.
        l: limit, list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """

    return XmlResponse(
        await EndDeviceListManager.fetch_enddevicelist_with_aggregator_id(
            db.session, request.state.aggregator_id, start=s[0], after=a[0], limit=l[0]
        )
    )


@router.post("/edev", status_code=201)
async def create_end_device(
    request: Request,
    response: Response,
    payload: EndDeviceRequest = Depends(XmlRequest(EndDeviceRequest)),
):
    """An EndDevice resource is generated with a unique reg_no (registration number).
    This reg_no is used to set the resource path i.e.'/edev/reg_no' which is
    sent to the client in the response 'Location' header.

    Args:
        response: fastapi.Response object.
        payload: The request payload/body object.

    Returns:
        fastapi.Response object.

    """
    try:
        site_id = await EndDeviceManager.add_or_update_enddevice_for_aggregator(
            db.session, request.state.aggregator_id, payload
        )

        response.headers["location"] = f"/edev/{site_id}"
    except IntegrityError as exc:
        logger.debug(exc)
        raise HTTPException(detail="lFDI conflict.", status_code=409)

    # TODO: different status_code if update
