import logging
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, HTTPException, Response, Query
from sqlalchemy.exc import NoResultFound, IntegrityError
from asyncpg.exceptions import CardinalityViolationError  # type: ignore
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.pricing import TariffManager, TariffListManager, TariffGeneratedRateListManager
from envoy.admin.schema.pricing import (
    TariffRequest,
    TariffResponse,
    TariffGeneratedRateRequest,
)
from envoy.admin.schema.uri import (
    TariffCreateUri,
    TariffUpdateUri,
    TariffGeneratedRateCreateUri,
)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(TariffCreateUri, status_code=HTTPStatus.OK, response_model=List[TariffResponse])
async def get_all_tariffs(
    start: list[int] = Query([0]),
    limit: list[int] = Query([5]),
) -> List[TariffResponse]:
    """Endpoint for a paginated list of TariffResponse Objects, ordered by changed_time datetime attribute (descending).


    Query Param:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 5.

    Returns:
        List[TariffResponse]

    """
    return await TariffListManager.fetch_many_tariffs(db.session, start[0], limit[0])


@router.get(TariffUpdateUri, status_code=HTTPStatus.OK, response_model=TariffResponse)
async def get_tariff(tariff_id: int):
    """Fetch a singular TariffResponse Object.

    Path Param:
        tariff_id: integer ID of the desired tariff resource.
    Returns:
        TariffResponse
    """
    return await TariffManager.fetch_tariff(db.session, tariff_id)


@router.post(TariffCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_tariff(tariff: TariffRequest, response: Response) -> None:
    """Creates a singular tariff. The location (/tariff/{tariff_id}) of the created resource is provided in the
    'Location' header of the response.

    Body:
        TariffRequest object.

    Returns:
        None
    """
    tariff_id = await TariffManager.add_new_tariff(db.session, tariff)
    response.headers["Location"] = TariffUpdateUri.format(tariff_id=tariff_id)


@router.put(TariffUpdateUri, status_code=HTTPStatus.OK, response_model=None)
async def update_tariff(tariff_id: int, tariff: TariffRequest) -> None:
    """Updates a tariff object.

    Path Params:
        tariff_id: integer ID of the desired tariff resource.

    Body:
        TariffRequest object.

    Returns:
        None
    """
    try:
        await TariffManager.update_existing_tariff(db.session, tariff_id, tariff)
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(detail="Not found", status_code=HTTPStatus.NOT_FOUND)


@router.post(TariffGeneratedRateCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_tariff_genrate(tariff_generates: List[TariffGeneratedRateRequest]) -> None:
    """Bulk creation of 'Tariff Generated Rates' associated with a particular Tariff and Site.

    Path Params:
        tariff_id: integer ID of the desired tariff resource.

    Body:
        List of TariffGeneratedRateRequest objects.

    Returns:
        None
    """
    try:
        await TariffGeneratedRateListManager.add_many_tariff_genrate(db.session, tariff_generates)

    except CardinalityViolationError as exc:
        logger.debug(exc)
        raise HTTPException(detail="The request contains duplicate instances", status_code=HTTPStatus.BAD_REQUEST)

    except IntegrityError as exc:
        logger.debug(exc)
        raise HTTPException(detail="tariff_id or site_id not found", status_code=HTTPStatus.BAD_REQUEST)
