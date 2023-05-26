import logging
from http import HTTPStatus
from typing import Union, List

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.exc import IntegrityError, NoResultFound
from fastapi_async_sqlalchemy import db

from envoy.admin.api.manager.pricing import TariffManager
from envoy.admin.schema.pricing import TariffRequest
from envoy.admin.schema.uri import TariffCreateUri, TariffUpdateUri


logger = logging.getLogger(__name__)

router = APIRouter()


# @router.get(TariffCreateUri, status_code=HTTPStatus.OK, response_model=List[TariffRequest])
# async def get_all_tariffs():
#     pass


@router.post(TariffCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_tariff(tariff: TariffRequest, response: Response) -> Union[None, Response]:
    """

    Responses will be static

    Returns:
        fastapi.Response object.
    """
    location = TariffUpdateUri.format(tariff_id=tariff.tariff_id)
    try:
        await TariffManager.add_new_tariff(db.session, tariff)
        response.headers["Location"] = location
    except IntegrityError as exc:
        logger.debug(exc)
        raise HTTPException(detail=f"tariff_id already exists at {location}", status_code=HTTPStatus.BAD_REQUEST)


@router.put(TariffUpdateUri, status_code=HTTPStatus.OK, response_model=None)
async def create_or_update_tariff(tariff_id: int, tariff: TariffRequest) -> Union[None, Response]:
    """

    Responses will be static

    Returns:
        fastapi.Response object.
    """
    if tariff.tariff_id != tariff_id:
        raise HTTPException(detail="tariff_id Mistmatch.", status_code=HTTPStatus.BAD_REQUEST)

    try:
        await TariffManager.update_existing_tariff(db.session, tariff)
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(detail="Not found", status_code=HTTPStatus.NOT_FOUND)
