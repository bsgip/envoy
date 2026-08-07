import logging
from datetime import datetime
from http import HTTPStatus

from asyncpg.exceptions import CardinalityViolationError
from envoy_schema.admin.schema.base import BatchCreateCollidableResponse, BatchCreateResponse, OnCollide
from envoy_schema.admin.schema.pricing import (
    TariffComponentRequest,
    TariffComponentResponse,
    TariffGeneratedRatePageResponse,
    TariffGeneratedRateRequest,
    TariffGeneratedRateResponse,
    TariffPageResponse,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.admin.schema.uri import (
    TariffComponentCreateUri,
    TariffComponentListUri,
    TariffComponentUpdateUri,
    TariffGeneratedRateCreateUri,
    TariffGeneratedRateListUri,
    TariffGeneratedRateUpdateUri,
    TariffListUri,
    TariffUpdateUri,
)
from fastapi import APIRouter, Query, Response
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import IntegrityError, NoResultFound

from envoy.admin.manager.pricing import (
    TariffComponentManager,
    TariffGeneratedRateManager,
    TariffManager,
)
from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import MAX_LIMIT, extract_limit_from_paging_param, extract_start_from_paging_param

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

    return await TariffManager.fetch_many_tariffs(
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
async def create_tariff(tariff: TariffRequest, response: Response) -> BatchCreateResponse:
    """Creates a singular tariff. The location (/tariff/{tariff_id}) of the created resource is provided in the
    'Location' header of the response.

    Body:
        TariffRequest object.

    Returns:
        BatchCreateResponse
    """
    tariff_id = await TariffManager.add_new_tariff(db.session, tariff)
    response.headers["Location"] = TariffUpdateUri.format(tariff_id=tariff_id)
    return BatchCreateResponse(ids=[tariff_id])


@router.put(TariffUpdateUri, status_code=HTTPStatus.NO_CONTENT, response_model=None)
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
    except IntegrityError as exc:
        raise LoggedHttpException(
            logger,
            exc,
            HTTPStatus.BAD_REQUEST,
            "Specified foreign key value does not exist (eg required_site_group_id)",
        ) from exc


@router.get(
    TariffComponentUpdateUri,
    status_code=HTTPStatus.OK,
    response_model=TariffComponentResponse,
)
async def get_tariff_component(tariff_component_id: int) -> TariffComponentResponse:
    """Fetch a singular TariffComponentResponse Object.

    Path Param:
        tariff_component_id: integer ID of the desired tariff component resource.
    Returns:
        TariffComponentResponse
    """
    try:
        return await TariffComponentManager.fetch_tariff_component(db.session, tariff_component_id)
    except NoResultFound as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "Not found") from exc


@router.put(TariffComponentUpdateUri, status_code=HTTPStatus.NO_CONTENT, response_model=None)
async def update_tariff_component(tariff_component_id: int, tariff_component: TariffComponentRequest) -> None:
    """Updates a singular TariffComponent with the new values.

    Path Param:
        tariff_component_id: integer ID of the desired tariff component resource.
    Returns:
        TariffComponentResponse
    """
    try:
        await TariffComponentManager.update_tariff_component(db.session, tariff_component_id, tariff_component)
    except NoResultFound as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "Not found") from exc


@router.delete(TariffComponentUpdateUri, status_code=HTTPStatus.NO_CONTENT, response_model=None)
async def delete_tariff_component(tariff_component_id: int) -> None:
    """Deletes (and archives) a singular TariffComponent - raising pub/sub notifications as required.

    Any existing TariffGeneratedRates will be archived too

    Path Param:
        tariff_component_id: integer ID of the desired tariff component resource.
    """
    try:
        await TariffComponentManager.delete_tariff_component(db.session, tariff_component_id)
    except NoResultFound as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "Not found") from exc


@router.post(
    TariffComponentCreateUri,
    status_code=HTTPStatus.CREATED,
    response_model=BatchCreateResponse,
)
async def create_tariff_component(tariff_component: TariffComponentRequest, response: Response) -> BatchCreateResponse:
    """Creates a singular tariff component. The location (/tariff_component/{tariff_id}) of the created resource is
    provided in the 'Location' header of the response.

    Body:
        TariffRequest object.

    Returns:
        BatchCreateResponse with a singular ID
    """

    try:
        tariff_component_id = await TariffComponentManager.add_new_tariff_component(db.session, tariff_component)
        response.headers["Location"] = TariffComponentUpdateUri.format(tariff_component_id=tariff_component_id)

        return BatchCreateResponse(ids=[tariff_component_id])
    except IntegrityError as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.BAD_REQUEST, "tariff_id or site_id not found") from exc


@router.get(
    TariffComponentListUri,
    status_code=HTTPStatus.OK,
    response_model=list[TariffComponentResponse],
)
async def get_tariff_components_for_tariff(tariff_id: int) -> list[TariffComponentResponse]:
    """List all TariffComponents belonging to a Tariff, ordered by tariff_component_id.

    Path Param:
        tariff_id: integer ID of the parent tariff.

    Returns:
        list[TariffComponentResponse]
    """
    try:
        return await TariffComponentManager.fetch_components_for_tariff(db.session, tariff_id)
    except NoResultFound as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "Not found") from exc


@router.post(TariffGeneratedRateCreateUri, status_code=HTTPStatus.CREATED, response_model=None)
async def create_tariff_genrate(
    tariff_generates: list[TariffGeneratedRateRequest],
    on_collide: OnCollide = Query(OnCollide.error),
) -> BatchCreateCollidableResponse:
    """Bulk creation of 'Tariff Generated Rates' associated with respective Tariffs (tariff_id) and Sites (site_id).

    A TariffGeneratedRate collides with another if they share the same (tariff_component_id, start_time,
    site_group_id).

    Body:
        List of TariffGeneratedRateRequest objects.

    Query Param:
        on_collide: How to handle a submitted entity that collides with an existing record. Default "error".
            error: Abort the entire operation - nothing will be written to the DB.
            ignore: Skip (don't insert) any colliding entities - the corresponding ID in the response will be -1.
            cancel: Cancel (archive/delete) any existing colliding entities before inserting the new entities.

    Returns:
        BatchCreateCollidableResponse - the ids list will correlate 1-1 with the submitted tariff_generates.
    """
    try:
        return await TariffGeneratedRateManager.add_many_tariff_genrate(db.session, tariff_generates, on_collide)

    except CardinalityViolationError as exc:
        raise LoggedHttpException(
            logger,
            exc,
            HTTPStatus.BAD_REQUEST,
            "The request contains duplicate instances",
        ) from exc

    except IntegrityError as exc:
        raise LoggedHttpException(
            logger,
            exc,
            HTTPStatus.BAD_REQUEST,
            "tariff_id or site_id not found, or a colliding TariffGeneratedRate already exists (see on_collide)",
        ) from exc


@router.get(
    TariffGeneratedRateUpdateUri,
    status_code=HTTPStatus.OK,
    response_model=TariffGeneratedRateResponse,
)
async def get_tariff_genrate(
    tariff_generated_rate_id: int,
) -> TariffGeneratedRateResponse:
    """Fetch a singular TariffGeneratedRateResponse Object.

    Path Param:
        tariff_generated_rate_id: integer ID of the desired tariff generated rate resource.
    Returns:
        TariffGeneratedRateResponse
    """
    try:
        return await TariffGeneratedRateManager.fetch_tariff_generated_rate(db.session, tariff_generated_rate_id)
    except NoResultFound as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "Not found") from exc


@router.delete(TariffGeneratedRateUpdateUri, status_code=HTTPStatus.NO_CONTENT, response_model=None)
async def delete_tariff_genrate(tariff_generated_rate_id: int) -> None:
    """Delete (cancel) a singular TariffGeneratedRateResponse. Will notify clients of cancellation.

    Path Param:
        tariff_generated_rate_id: integer ID of the desired tariff generated rate resource.
    Returns:
        TariffGeneratedRateResponse
    """
    try:
        return await TariffGeneratedRateManager.cancel_tariff_generated_rate(db.session, tariff_generated_rate_id)
    except NoResultFound as exc:
        raise LoggedHttpException(logger, exc, HTTPStatus.NOT_FOUND, "Not found") from exc


@router.get(
    TariffGeneratedRateListUri,
    status_code=HTTPStatus.OK,
    response_model=TariffGeneratedRatePageResponse,
)
async def get_tariff_genrates_for_component(
    tariff_component_id: int,
    start: int = Query(0),
    limit: int = Query(MAX_LIMIT),
    group: str | None = Query(None),
    start_time_since: datetime | None = Query(None),
    start_time_until: datetime | None = Query(None),
    site_id: int | None = Query(None),
) -> TariffGeneratedRatePageResponse:
    """List all TariffGeneratedRate belonging to a TariffComponent, ordered by tariff_generated_rate_id and optionally
    filtered.

    Path Param:
        tariff_component_id: integer ID of the parent tariff component.

    Query Param:
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 5. Max 500.
        group: SiteGroup name by which to filter returned tariffs (matches TariffGeneratedRate.site_group_id)
        start_time_since: Filter on start_time for the returned rates (lowest allowed value - Inclusive)
        start_time_until: Filter on start_time for the returned rates (highed allowed value - Exclusive)
        site_id: If set - only return rates whose site_group_id contains site_id as a member

    Returns:
        list[TariffComponentResponse]
    """

    return await TariffGeneratedRateManager.fetch_tariff_genrates(
        db.session,
        tariff_component_id=tariff_component_id,
        start=start,
        limit=limit,
        group=group,
        start_time_since=start_time_since,
        start_time_until=start_time_until,
        site_id=site_id,
    )
