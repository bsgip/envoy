import logging
from datetime import datetime
from http import HTTPStatus

from envoy_schema.admin.schema.archive import (
    ArchiveDynamicOperatingEnvelopeResponse,
    ArchivePageResponse,
    ArchiveSiteResponse,
    ArchiveTariffGeneratedRateResponse,
)
from envoy_schema.admin.schema.uri import (
    ArchiveForPeriodDoes,
    ArchiveForPeriodSites,
    ArchiveForPeriodTariffGeneratedRate,
)
from fastapi import APIRouter, Path, Query
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.archive import ArchiveListManager
from envoy.server.api.request import extract_limit_from_paging_param, extract_start_from_paging_param

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(ArchiveForPeriodSites, status_code=HTTPStatus.OK, response_model=ArchivePageResponse[ArchiveSiteResponse])
async def get_archived_sites_for_period(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
    period_start: datetime = Path(),
    period_end: datetime = Path(),
    only_deletes: bool = Query(True),
) -> ArchivePageResponse[ArchiveSiteResponse]:
    """Endpoint for a paginated list of archived Site Objects, ordered by archive_id that were created within a
    period of time. An archive is a moment in time snapshot of a record that was created before it was deleted/updated.

    Path Param:
        period_start: The (inclusive) start datetime to request data for (include timezone)
        period_end: The (exclusive) end datetime to request data for (include timezone)

    Query Param:
        only_deletes: False will return all change/delete archives, True will just return deletes. Default True
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 100. Max 500.

    Note - The period range will filter records based on archive_time if only_deletes=False or deleted_time otherwise

    Returns:
        ArchivePageResponse[ArchiveSiteResponse]
    """
    return await ArchiveListManager.get_archive_sites_for_period(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        period_start=period_start,
        period_end=period_end,
        only_deletes=only_deletes,
    )


@router.get(
    ArchiveForPeriodDoes,
    status_code=HTTPStatus.OK,
    response_model=ArchivePageResponse[ArchiveDynamicOperatingEnvelopeResponse],
)
async def get_archived_does_for_period(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
    period_start: datetime = Path(),
    period_end: datetime = Path(),
    only_deletes: bool = Query(True),
) -> ArchivePageResponse[ArchiveDynamicOperatingEnvelopeResponse]:
    """Endpoint for a paginated list of archived DOE Objects, ordered by archive_id that were created within a
    period of time. An archive is a moment in time snapshot of a record that was created before it was deleted/updated.

    Path Param:
        period_start: The (inclusive) start datetime to request data for (include timezone)
        period_end: The (exclusive) end datetime to request data for (include timezone)

    Query Param:
        only_deletes: False will return all change/delete archives, True will just return deletes. Default True
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 100. Max 500.

    Note - The period range will filter records based on archive_time if only_deletes=False or deleted_time otherwise

    Returns:
        ArchivePageResponse[ArchiveDynamicOperatingEnvelopeResponse]
    """
    return await ArchiveListManager.get_archive_does_for_period(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        period_start=period_start,
        period_end=period_end,
        only_deletes=only_deletes,
    )


@router.get(
    ArchiveForPeriodTariffGeneratedRate,
    status_code=HTTPStatus.OK,
    response_model=ArchivePageResponse[ArchiveTariffGeneratedRateResponse],
)
async def get_archived_rates_for_period(
    start: list[int] = Query([0]),
    limit: list[int] = Query([100]),
    period_start: datetime = Path(),
    period_end: datetime = Path(),
    only_deletes: bool = Query(True),
) -> ArchivePageResponse[ArchiveTariffGeneratedRateResponse]:
    """Endpoint for a paginated list of archived DOE Objects, ordered by archive_id that were created within a
    period of time. An archive is a moment in time snapshot of a record that was created before it was deleted/updated.

    Path Param:
        period_start: The (inclusive) start datetime to request data for (include timezone)
        period_end: The (exclusive) end datetime to request data for (include timezone)

    Query Param:
        only_deletes: False will return all change/delete archives, True will just return deletes. Default True
        start: start index value (for pagination). Default 0.
        limit: maximum number of objects to return. Default 100. Max 500.

    Note - The period range will filter records based on archive_time if only_deletes=False or deleted_time otherwise

    Returns:
        ArchivePageResponse[ArchiveTariffGeneratedRateResponse]
    """
    return await ArchiveListManager.get_archive_rates_for_period(
        session=db.session,
        start=extract_start_from_paging_param(start),
        limit=extract_limit_from_paging_param(limit),
        period_start=period_start,
        period_end=period_end,
        only_deletes=only_deletes,
    )
