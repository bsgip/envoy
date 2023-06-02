import logging
from http import HTTPStatus
from typing import Union

from fastapi import APIRouter, HTTPException, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError, NoResultFound

from envoy.admin.manager.doe import DoeManager
from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdmin
from envoy.admin.schema.uri import DoeCreateUri, DoeUpdateUri

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(DoeCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_doe(doe: DynamicOperatingEnvelopeAdmin, response: Response) -> Union[None, Response]:
    """

    Responses will be static

    Returns:
        fastapi.Response object.
    """
    location = DoeUpdateUri.format(doe_id=doe.dynamic_operating_envelope_id)
    try:
        await DoeManager.add_new_doe(db.session, doe)
        response.headers["Location"] = location
    except IntegrityError as exc:
        logger.debug(exc)
        raise HTTPException(detail=f"DOE already exists at {location}", status_code=HTTPStatus.BAD_REQUEST)


@router.put(DoeUpdateUri, status_code=HTTPStatus.OK, response_model=None)
async def create_or_update_tariff(doe_id: int, doe: DynamicOperatingEnvelopeAdmin) -> Union[None, Response]:
    """

    Responses will be static

    Returns:
        fastapi.Response object.
    """
    if doe.dynamic_operating_envelope_id != doe_id:
        raise HTTPException(detail="dynamic_operating_envelope_id mismatch.", status_code=HTTPStatus.BAD_REQUEST)

    try:
        await DoeManager.update_existing_doe(db.session, doe)
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(detail="Not found", status_code=HTTPStatus.NOT_FOUND)
