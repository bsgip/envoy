import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError
from asyncpg.exceptions import CardinalityViolationError  # type: ignore

from envoy.admin.manager.doe import DoeListManager
from envoy.admin.schema.doe import DynamicOperatingEnvelopeRequest
from envoy.admin.schema.uri import DoeCreateUri

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(DoeCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_doe(doe_list: list[DynamicOperatingEnvelopeRequest]) -> None:
    """Bulk creation of 'Dynamic Operating Envelopes'. Each DynamicOperatingEnvelope is associated
    with a Site object via the site_id attribute.

    Body:
        List of DynamicOperatingEnvelopeRequest objects.

    Returns:
        None
    """
    try:
        await DoeListManager.add_many_doe(db.session, doe_list)

    except CardinalityViolationError as exc:
        logger.debug(exc)
        raise HTTPException(detail="The request contains duplicate instances", status_code=HTTPStatus.BAD_REQUEST)

    except IntegrityError as exc:
        logger.debug(exc)
        raise HTTPException(detail="site_id not found", status_code=HTTPStatus.BAD_REQUEST)
