from envoy_schema.admin.schema.cleanup import (
    ArchiveCleanupRequest,
    ArchiveCleanupResponse,
    ArchiveCleanupType,
    CleanupResponse,
    ExpiredCleanupMode,
    ExpiredCleanupRequest,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.cleanup import (
    delete_archive_records,
    delete_expired_site_controls,
    delete_expired_tariff_generated_rates,
)
from envoy.server.manager.time import utc_now
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.archive.doe import (
    ArchiveDynamicOperatingEnvelope,
    ArchiveSiteControlGroup,
    ArchiveSiteControlGroupDefault,
)
from envoy.server.model.archive.server import ArchiveRuntimeServerConfig
from envoy.server.model.archive.site import (
    ArchiveSite,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
    ArchiveSiteGroup,
    ArchiveSiteGroupAssignment,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.archive.subscription import ArchiveSubscription, ArchiveSubscriptionCondition
from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffGeneratedRate

# Maps each ArchiveCleanupType to the archive table it targets. A value of None indicates that this utility server
# doesn't have an archive table for that type (so there is never anything to remove)
ARCHIVE_TABLE_BY_CLEANUP_TYPE: dict[ArchiveCleanupType, type[ArchiveBase] | None] = {
    ArchiveCleanupType.site: ArchiveSite,
    ArchiveCleanupType.site_group: ArchiveSiteGroup,
    ArchiveCleanupType.site_group_assignment: ArchiveSiteGroupAssignment,
    ArchiveCleanupType.site_der_rating: ArchiveSiteDERRating,
    ArchiveCleanupType.site_der_setting: ArchiveSiteDERSetting,
    ArchiveCleanupType.site_der_availability: ArchiveSiteDERAvailability,
    ArchiveCleanupType.site_der_status: ArchiveSiteDERStatus,
    ArchiveCleanupType.site_reading_type: ArchiveSiteReadingType,
    ArchiveCleanupType.site_reading: ArchiveSiteReading,
    ArchiveCleanupType.site_control_group: ArchiveSiteControlGroup,
    ArchiveCleanupType.site_control_group_default: ArchiveSiteControlGroupDefault,
    ArchiveCleanupType.site_control: ArchiveDynamicOperatingEnvelope,
    ArchiveCleanupType.tariff: ArchiveTariff,
    ArchiveCleanupType.tariff_component: None,  # No TariffComponent table exists in v1.2
    ArchiveCleanupType.tariff_generated_rate: ArchiveTariffGeneratedRate,
    ArchiveCleanupType.subscription: ArchiveSubscription,
    ArchiveCleanupType.subscription_condition: ArchiveSubscriptionCondition,
    ArchiveCleanupType.runtime_server_config: ArchiveRuntimeServerConfig,
}


class CleanupManager:
    """Handles the bulk removal of old/expired data from the database.

    NOTE: Removing expired entities will NOT generate subscription notifications. By definition, these entities are no
    longer active so clients have no need to be informed of their removal (and the volume of notifications could be
    enormous)."""

    @staticmethod
    async def cleanup_expired_site_controls(session: AsyncSession, request: ExpiredCleanupRequest) -> CleanupResponse:
        """Removes all site controls (across all SiteControlGroups) that have expired at request.expired_before"""
        removed_count = await delete_expired_site_controls(
            session,
            expired_before=request.expired_before,
            archive=request.mode == ExpiredCleanupMode.archive,
            deleted_time=utc_now(),
        )
        await session.commit()
        return CleanupResponse(removed_count=removed_count)

    @staticmethod
    async def cleanup_expired_tariff_generated_rates(
        session: AsyncSession, request: ExpiredCleanupRequest
    ) -> CleanupResponse:
        """Removes all tariff generated rates (across all tariffs) that have expired at request.expired_before"""
        removed_count = await delete_expired_tariff_generated_rates(
            session,
            expired_before=request.expired_before,
            archive=request.mode == ExpiredCleanupMode.archive,
            deleted_time=utc_now(),
        )
        await session.commit()
        return CleanupResponse(removed_count=removed_count)

    @staticmethod
    async def cleanup_archives(session: AsyncSession, request: ArchiveCleanupRequest) -> ArchiveCleanupResponse:
        """Permanently deletes archive records (from the requested archive tables) whose archive_time is at or before
        request.archived_before. If request.archive_types is None, every archive table will be targeted."""

        archive_types: list[ArchiveCleanupType]
        if request.archive_types is None:
            archive_types = list(ArchiveCleanupType)
        else:
            archive_types = list(dict.fromkeys(request.archive_types))  # dedupe - preserving order

        removed_counts: dict[ArchiveCleanupType, int] = {}
        for archive_type in archive_types:
            archive_table = ARCHIVE_TABLE_BY_CLEANUP_TYPE[archive_type]
            if archive_table is None:
                removed_counts[archive_type] = 0
            else:
                removed_counts[archive_type] = await delete_archive_records(
                    session, archive_table, request.archived_before
                )

        await session.commit()
        return ArchiveCleanupResponse(archived_before=request.archived_before, removed_counts=removed_counts)
