import logging
from http import HTTPStatus
from typing import Union

from fastapi import APIRouter, HTTPException, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import NoResultFound

from envoy.admin.manager.doe import DoeManager
from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdminRequest, DynamicOperatingEnvelopeAdminResponse
from envoy.admin.schema.uri import DoeCreateUri, DoeUpdateUri

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(DoeUpdateUri, status_code=HTTPStatus.OK, response_model=DynamicOperatingEnvelopeAdminResponse)
async def get_doe(doe_id: int) -> Union[None, Response]:
    """Returns exactly one DOE from the db."""
    return await DoeManager.fetch_doe(db.session, doe_id)


@router.post(DoeCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_doe(doe: DynamicOperatingEnvelopeAdminRequest, response: Response) -> Union[None, Response]:
    """Creates exactly one DOE and adds it the db. Updates the response headers with the
    location of the created resource. Returns None."""

    doe_id = await DoeManager.add_new_doe(db.session, doe)
    response.headers["Location"] = DoeUpdateUri.format(doe_id=doe_id)


@router.put(DoeUpdateUri, status_code=HTTPStatus.OK, response_model=None)
async def update_doe(doe_id: int, doe: DynamicOperatingEnvelopeAdminRequest) -> None:
    """Updates exactly one pre-existing DOE in the db. Returns None, or raises
    HTTP.NOT_FOUND if the DOE was not found in the db."""

    try:
        await DoeManager.update_existing_doe(db.session, doe_id, doe)
    except NoResultFound as exc:
        logger.debug(exc)
        raise HTTPException(detail="Not found", status_code=HTTPStatus.NOT_FOUND)
