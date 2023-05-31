import logging
from http import HTTPStatus
from typing import Union, List

from fastapi import APIRouter, HTTPException, Response, Query
from sqlalchemy.exc import NoResultFound
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.pricing import TariffManager, TariffListManager, TariffGeneratedRateManager
from envoy.admin.schema.pricing import TariffRequest, TariffResponse, TariffGeneratedRateRequest
from envoy.admin.schema.uri import (
    TariffCreateUri,
    TariffUpdateUri,
    TariffGeneratedRateCreateUri,
    TariffGeneratedRateUpdateUri,
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


@router.get(TariffUpdateUri, status_code=HTTPStatus.OK, response_model=List[TariffResponse])
async def get_tariff(tariff_id: int):
    """Fetch a singular TariffResponse Object.

    Path Param:
        tariff_id: integer ID of the desired tariff resource.
    Returns:
        TariffResponse
    """
    return await TariffManager.fetch_tariff(db.session, tariff_id)


@router.post(TariffCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_tariff(tariff: TariffRequest, response: Response) -> Union[None, Response]:
    """Creates a singular tariff. The location (/tariff/{tariff_id}) of the created resource is provided in the 'Location' header of the response.

    Body:
        TariffRequest object.

    Returns:
        None
    """
    tariff_id = await TariffManager.add_new_tariff(db.session, tariff)
    response.headers["Location"] = TariffUpdateUri.format(tariff_id=tariff_id)


@router.put(TariffUpdateUri, status_code=HTTPStatus.OK, response_model=None)
async def update_tariff(tariff_id: int, tariff: TariffRequest) -> Union[None, Response]:
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


@router.post(TariffGeneratedRateCreateUri, status_code=HTTPStatus.OK, response_model=None)
async def create_tariff_genrate(
    tariff_id: int, tariff_generate: TariffGeneratedRateRequest, response: Response
) -> Union[None, Response]:
    """Creates a Tariff Generated Rate associated with a pacticular Tariff and Site. The location (/tariff/{tariff_id}/{tariff_generated_rate_id}) of the created resource is provided in the 'Location' header of the response.

    Path Params:
        tariff_id: integer ID of the desired tariff resource.

    Body:
        TariffGeneratedRateRequest object.

    Returns:
        None
    """
    if tariff_generate.tariff_id != tariff_id:
        raise HTTPException(detail="tariff_id Mistmatch.", status_code=HTTPStatus.BAD_REQUEST)

    try:
        tariff_genrate_id = await TariffGeneratedRateManager.add_tariff_genrate(db.session, tariff_generate)
        response.headers["Location"] = TariffGeneratedRateUpdateUri.format(
            tariff_id=tariff_id, tariff_generated_rate_id=tariff_genrate_id
        )
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(detail="tariff_id or site_id not found.", status_code=HTTPStatus.BAD_REQUEST)
