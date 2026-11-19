import logging
from http import HTTPStatus

from envoy_schema.admin.schema.cleanup import (
    ArchiveCleanupRequest,
    ArchiveCleanupResponse,
    CleanupResponse,
    ExpiredCleanupRequest,
)
from envoy_schema.admin.schema.uri import (
    CleanupArchiveUri,
    CleanupExpiredSiteControlsUri,
    CleanupExpiredTariffGeneratedRatesUri,
)
from fastapi import APIRouter
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.cleanup import CleanupManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(CleanupExpiredSiteControlsUri, status_code=HTTPStatus.OK, response_model=CleanupResponse)
async def cleanup_expired_site_controls(request: ExpiredCleanupRequest) -> CleanupResponse:
    """Removes ALL site controls (across every site control group) whose end time (start_time + duration_seconds) is
    at or before expired_before. Controls that are active or yet to start at expired_before are unaffected.

    Depending on mode, removed controls will either be copied to the archive (archive) or permanently deleted (delete).

    NOTE: No subscription notifications will be raised for removed controls.

    Body:
        ExpiredCleanupRequest

    Returns:
        CleanupResponse
    """
    response = await CleanupManager.cleanup_expired_site_controls(db.session, request)
    logger.info(
        f"Cleanup of expired site controls (mode={request.mode}) before {request.expired_before} "
        f"removed {response.removed_count} records"
    )
    return response


@router.post(CleanupExpiredTariffGeneratedRatesUri, status_code=HTTPStatus.OK, response_model=CleanupResponse)
async def cleanup_expired_tariff_generated_rates(request: ExpiredCleanupRequest) -> CleanupResponse:
    """Removes ALL tariff generated rates (across every tariff) whose end time (start_time + duration_seconds) is at or
    before expired_before. Rates that are active or yet to start at expired_before are unaffected.

    Depending on mode, removed rates will either be copied to the archive (archive) or permanently deleted (delete).

    NOTE: No subscription notifications will be raised for removed rates.

    Body:
        ExpiredCleanupRequest

    Returns:
        CleanupResponse
    """
    response = await CleanupManager.cleanup_expired_tariff_generated_rates(db.session, request)
    logger.info(
        f"Cleanup of expired tariff generated rates (mode={request.mode}) before {request.expired_before} "
        f"removed {response.removed_count} records"
    )
    return response


@router.post(CleanupArchiveUri, status_code=HTTPStatus.OK, response_model=ArchiveCleanupResponse)
async def cleanup_archive(request: ArchiveCleanupRequest) -> ArchiveCleanupResponse:
    """Permanently deletes archive records whose archive_time is at or before archived_before. If archive_types is
    not specified, ALL archive tables will be targeted.

    Body:
        ArchiveCleanupRequest

    Returns:
        ArchiveCleanupResponse
    """
    response = await CleanupManager.cleanup_archives(db.session, request)
    logger.info(f"Cleanup of archives before {request.archived_before} removed {response.removed_counts}")
    return response
