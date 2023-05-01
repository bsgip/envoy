import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError, NoResultFound

from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.manager.end_device import EndDeviceListManager, EndDeviceManager
from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.schema.sep2.end_device import EndDeviceRequest

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head("/edev/{site_id}")
@router.get(
    "/edev/{site_id}",
    status_code=HTTPStatus.OK,
)
async def get_enddevice(site_id: int, request: Request) -> XmlResponse:
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
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")

    if end_device is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(end_device)


@router.head("/edev")
@router.get(
    "/edev",
    status_code=HTTPStatus.OK,
)
async def get_enddevice_list(
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a EndDeviceList resource.

    Args:
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """

    return XmlResponse(
        await EndDeviceListManager.fetch_enddevicelist_with_aggregator_id(
            db.session, request.state.aggregator_id, start=start[0], after=after[0], limit=limit[0]
        )
    )


@router.post("/edev", status_code=HTTPStatus.CREATED)
async def create_end_device(
    request: Request,
    payload: EndDeviceRequest = Depends(XmlRequest(EndDeviceRequest)),
) -> Response:
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
        return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: f"/edev/{site_id}"})
    except InvalidMappingError as exc:
        logger.debug(exc)
        raise HTTPException(detail=exc.message, status_code=HTTPStatus.BAD_REQUEST)
    except IntegrityError as exc:
        logger.debug(exc)
        raise HTTPException(detail="lFDI conflict.", status_code=HTTPStatus.CONFLICT)
