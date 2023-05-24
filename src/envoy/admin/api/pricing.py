import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Response
from fastapi_async_sqlalchemy import db

from envoy.admin.schema.uri import TariffUri
from envoy.admin.schema.pricing import TariffRequest
from envoy.admin.api.manager.pricing import TariffManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.put(TariffUri, status_code=HTTPStatus.CREATED)
async def create_or_update_tariff(tariff_id: int, tariff: TariffRequest, response: Response) -> int:
    """

    Responses will be static

    Returns:
        fastapi.Response object.
    """
    if tariff.tariff_id != tariff_id:
        raise HTTPException(detail="tariff_id Mistmatch.", status_code=HTTPStatus.BAD_REQUEST)

    update = await TariffManager.add_or_update_tariff(db.session, tariff)

    if update:
        response.status_code = HTTPStatus.OK
