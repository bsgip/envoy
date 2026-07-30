import logging
from http import HTTPStatus

from asyncpg.exceptions import CardinalityViolationError
from envoy_schema.admin.schema.pricing import (
    TariffGeneratedRateRequest,
    TariffPageResponse,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.admin.schema.uri import TariffGeneratedRateCreateUri, TariffListUri, TariffUpdateUri
from fastapi import APIRouter, Query, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError, NoResultFound

from envoy.admin.manager.pricing import TariffGeneratedRateListManager, TariffListManager, TariffManager
from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(TariffListUri, status_code=HTTPStatus.OK, response_model=TariffPageResponse)
async def get_all_tariffs(
    start: list[int] = Query([0]),
    limit: list[int] = Query([5]),
    group: list[str] = Query([]),
) -> TariffPageResponse:
    """Endpoint for a paginated list of TariffResponse Objects, ordered by tariff_id attribute (descending).

    Query Param:
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 5. Max 500.
        group: SiteGroup name by which to filter returned tariffs (matches Tariff.required_site_group_id against
            the named SiteGroup OR any Tariff with a null required_site_group_id). Default no filter

    Returns:
        TariffPageResponse

    """
    group_filter: str | None = None
    if group is not None and len(group) > 0:
        group_filter = group[0]

    return await TariffListManager.fetch_many_tariffs(
        db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        group_filter=group_filter,
    )


@router.get(TariffUpdateUri, status_code=HTTPStatus.OK, response_model=TariffResponse)
async def get_tariff(tariff_id: int) -> TariffResponse:
    """Fetch a singular TariffResponse Object.

    Path Param:
        tariff_id: integer ID of the desired tariff resource.
    Returns:
        TariffResponse
    """
    return await TariffManager.fetch_tariff(db.session, tariff_id)


@router.post(TariffListUri, status_code=HTTPStatus.CREATED, response_model=None)
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
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "Not found") from exc


@router.post(TariffGeneratedRateCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_tariff_genrate(tariff_generates: list[TariffGeneratedRateRequest]) -> None:
    """Bulk creation of 'Tariff Generated Rates' associated with respective Tariffs (tariff_id) and Sites (site_id).

    Body:
        List of TariffGeneratedRateRequest objects.

    Returns:
        None
    """
    try:
        await TariffGeneratedRateListManager.add_many_tariff_genrate(db.session, tariff_generates)

    except CardinalityViolationError as exc:
        raise LoggedHttpException(
            logger, exc, HTTPStatus.BAD_REQUEST, "The request contains duplicate instances"
        ) from exc

    except IntegrityError as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.BAD_REQUEST, "tariff_id or site_id not found") from exc
