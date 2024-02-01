import logging
from http import HTTPStatus

from asyncpg.exceptions import CardinalityViolationError  # type: ignore
from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest
from envoy_schema.admin.schema.uri import DoeCreateUri
from fastapi import APIRouter
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError

from envoy.admin.manager.doe import DoeListManager
from envoy.server.api.error_handler import LoggedHttpException

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
        raise LoggedHttpException(logger, exc, HTTPStatus.BAD_REQUEST, "The request contains duplicate instances")

    except IntegrityError as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.BAD_REQUEST, "site_id not found")
