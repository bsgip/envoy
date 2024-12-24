from datetime import datetime

from envoy_schema.admin.schema.archive import (
    ArchiveDynamicOperatingEnvelopeResponse,
    ArchivePageResponse,
    ArchiveSiteResponse,
    ArchiveTariffGeneratedRateResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.archive import (
    count_archive_does_for_period,
    count_archive_rates_for_period,
    count_archive_sites_for_period,
    select_archive_does_for_period,
    select_archive_rates_for_period,
    select_archive_sites_for_period,
)
from envoy.admin.mapper.archive import ArchiveListMapper


class ArchiveListManager:

    @staticmethod
    async def get_archive_sites_for_period(
        session: AsyncSession, start: int, limit: int, period_start: datetime, period_end: datetime, only_deletes: bool
    ) -> ArchivePageResponse[ArchiveSiteResponse]:
        """Admin specific (paginated) fetch of archived site records that covers all aggregators."""
        archive_count = await count_archive_sites_for_period(
            session, period_start=period_start, period_end=period_end, only_deletes=only_deletes
        )
        archive_records = await select_archive_sites_for_period(
            session,
            period_start=period_start,
            period_end=period_end,
            only_deletes=only_deletes,
            start=start,
            limit=limit,
        )
        return ArchiveListMapper.map_to_sites_response(
            total_count=archive_count,
            limit=limit,
            start=start,
            period_start=period_start,
            period_end=period_end,
            sites=archive_records,
        )

    @staticmethod
    async def get_archive_does_for_period(
        session: AsyncSession, start: int, limit: int, period_start: datetime, period_end: datetime, only_deletes: bool
    ) -> ArchivePageResponse[ArchiveDynamicOperatingEnvelopeResponse]:
        """Admin specific (paginated) fetch of archived doe records that covers all aggregators."""
        archive_count = await count_archive_does_for_period(
            session, period_start=period_start, period_end=period_end, only_deletes=only_deletes
        )
        archive_records = await select_archive_does_for_period(
            session,
            period_start=period_start,
            period_end=period_end,
            only_deletes=only_deletes,
            start=start,
            limit=limit,
        )
        return ArchiveListMapper.map_to_does_response(
            total_count=archive_count,
            limit=limit,
            start=start,
            period_start=period_start,
            period_end=period_end,
            does=archive_records,
        )

    @staticmethod
    async def get_archive_rates_for_period(
        session: AsyncSession, start: int, limit: int, period_start: datetime, period_end: datetime, only_deletes: bool
    ) -> ArchivePageResponse[ArchiveTariffGeneratedRateResponse]:
        """Admin specific (paginated) fetch of archived rate records that covers all aggregators."""
        archive_count = await count_archive_rates_for_period(
            session, period_start=period_start, period_end=period_end, only_deletes=only_deletes
        )
        archive_records = await select_archive_rates_for_period(
            session,
            period_start=period_start,
            period_end=period_end,
            only_deletes=only_deletes,
            start=start,
            limit=limit,
        )
        return ArchiveListMapper.map_to_rates_response(
            total_count=archive_count,
            limit=limit,
            start=start,
            period_start=period_start,
            period_end=period_end,
            rates=archive_records,
        )
