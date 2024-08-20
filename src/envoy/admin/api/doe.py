import logging
from datetime import datetime
from http import HTTPStatus
from typing import Optional

from asyncpg.exceptions import CardinalityViolationError  # type: ignore
from envoy_schema.admin.schema.doe import DoePageResponse, DynamicOperatingEnvelopeRequest
from envoy_schema.admin.schema.uri import DoeUri
from fastapi import APIRouter, Query
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError

from envoy.admin.manager.doe import DoeListManager
from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(DoeUri, status_code=HTTPStatus.CREATED, response_model=None)
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


@router.get(DoeUri, status_code=HTTPStatus.OK, response_model=DoePageResponse)
async def get_all_does(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
    after: Optional[datetime] = Query(None),
) -> DoePageResponse:
    """Endpoint for a paginated list of DynamicOperatingEnvelope Objects, ordered by dynamic_operating_envelope_id
    attribute.

    Query Param:
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 100. Max 500.
        after: Filters objects that have been created/modified after this timestamp (inclusive). Default no filter.

    Returns:
        DoePageResponse
    """
    return await DoeListManager.get_all_does(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        changed_after=after,
    )
