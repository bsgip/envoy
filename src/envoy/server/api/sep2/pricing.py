import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import NoResultFound

from envoy.server.api.response import XmlResponse

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head("/tp")
@router.get("/tp", status_code=HTTPStatus.OK)
async def get_tariffprofilelist(request: Request,
                                start: list[int] = Query([0], alias="s"),
                                after: list[int] = Query([0], alias="a"),
                                limit: list[int] = Query([1], alias="l"),) -> XmlResponse:
    """Responds with a paginated list of tariff profiles available to the current client.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    raise NotImplementedError()


@router.head("/tp/{tariff_id}")
@router.get("/tp/{tariff_id}", status_code=HTTPStatus.OK)
async def get_singletariffprofile(tariff_id: int, request: Request) -> XmlResponse:
    """Responds with a single TariffProfile resource identified by tariff_id.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        raise NotImplementedError()
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head("/tp/{tariff_id}/rc")
@router.get("/tp/{tariff_id}/rc", status_code=HTTPStatus.OK)
async def get_ratecomponentlist(tariff_id: int,
                                request: Request,
                                start: list[int] = Query([0], alias="s"),
                                after: list[int] = Query([0], alias="a"),
                                limit: list[int] = Query([1], alias="l"),) -> XmlResponse:
    """Responds with a paginated list of RateComponents belonging to tariff_id.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        raise NotImplementedError()
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head("/tp/{tariff_id}/rc/{rate_component_id}")
@router.get("/tp/{tariff_id}/rc/{rate_component_id}", status_code=HTTPStatus.OK)
async def get_singleratecomponent(tariff_id: int,
                                  rate_component_id: str,
                                  request: Request) -> XmlResponse:
    """Responds with a single RateComponent resource identified by the parent tariff_id and target rate_component_id.


    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        raise NotImplementedError()
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head("/tp/{tariff_id}/rc/{rate_component_id}/tti")
@router.get("/tp/{tariff_id}/rc/{rate_component_id}/tti", status_code=HTTPStatus.OK)
async def get_timetariffintervallist(tariff_id: int,
                                     rate_component_id: str,
                                     request: Request,
                                     start: list[int] = Query([0], alias="s"),
                                     after: list[int] = Query([0], alias="a"),
                                     limit: list[int] = Query([1], alias="l"),) -> XmlResponse:
    """Responds with a paginated list of TimeTariffInterval entities belonging to the specified tariff/rate_component.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        raise NotImplementedError()
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head("/tp/{tariff_id}/rc/{rate_component_id}/tti/{tti_id}")
@router.get("/tp/{tariff_id}/rc/{rate_component_id}/tti/{tti_id}", status_code=HTTPStatus.OK)
async def get_singletimetariffinterval(tariff_id: int,
                                       rate_component_id: str,
                                       tti_id: str,
                                       request: Request) -> XmlResponse:
    """Responds with a single TimeTariffInterval resource identified by the set of ID's.


    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        tti_id: Path parameter, the target TimeTariffInterval id (should be a time in 24 hour HH:MM format)
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        raise NotImplementedError()
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head("/tp/{tariff_id}/rc/{rate_component_id}/tti/{tti_id}/cti")
@router.get("/tp/{tariff_id}/rc/{rate_component_id}/tti/{tti_id}/cti", status_code=HTTPStatus.OK)
async def get_consumptiontariffintervallist(tariff_id: int,
                                            rate_component_id: str,
                                            tti_id: str,
                                            price: int,
                                            request: Request,
                                            start: list[int] = Query([0], alias="s"),
                                            after: list[int] = Query([0], alias="a"),
                                            limit: list[int] = Query([1], alias="l"),) -> XmlResponse:
    """Responds with a paginated list of ConsumptionTariffInterval belonging to specified parent ids.

    This endpoint is not necessary as it will always return a single price that is already encoded in the URI. It's
    implemented for the purposes of remaining 2030.5 compliant but clients to this implementation can avoid this call

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        tti_id: Path parameter, the target TimeTariffInterval id (should be a time in 24 hour HH:MM format)
        price: The price encoded in the URI from the parent TimeTariffInterval.ConsumptionTariffIntervalListLink href
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        raise NotImplementedError()
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")


@router.head("/tp/{tariff_id}/rc/{rate_component_id}/tti/{tti_id}/cti/{price}")
@router.get("/tp/{tariff_id}/rc/{rate_component_id}/tti/{tti_id}/cti/{price}", status_code=HTTPStatus.OK)
async def get_singleconsumptiontariffinterval(tariff_id: int,
                                              rate_component_id: str,
                                              tti_id: str,
                                              price: int,
                                              request: Request) -> XmlResponse:
    """Responds with a single ConsumptionTariffInterval resource.

    This endpoint is not necessary as it will always return a single price that is already encoded in the URI. It's
    implemented for the purposes of remaining 2030.5 compliant but clients to this implementation can avoid this call

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        tti_id: Path parameter, the target TimeTariffInterval id (should be a time in 24 hour HH:MM format)
        price: The price encoded in the URI from the parent TimeTariffInterval.ConsumptionTariffIntervalListLink href
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        raise NotImplementedError()
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")