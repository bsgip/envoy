from datetime import datetime
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.site_reading import (
    count_site_readings_for_sites_and_time,
    select_site_readings_for_sites_and_time,
)
from envoy.server.model.site_reading import SiteReading


class AdminSiteReadingManager:
    """Logic layer for admin site reading operations."""

    @staticmethod
    async def get_site_readings_for_sites_and_time(
        session: AsyncSession,
        site_ids: list[int],
        start_time: datetime,
        end_time: datetime,
        start: int = 0,
        limit: int = 1000,
    ) -> Sequence[SiteReading]:
        """Get site readings for specified sites within a time range."""
        return await select_site_readings_for_sites_and_time(
            session=session,
            site_ids=site_ids,
            start_time=start_time,
            end_time=end_time,
            start=start,
            limit=limit,
        )

    @staticmethod
    async def count_site_readings_for_sites_and_time(
        session: AsyncSession,
        site_ids: list[int],
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Count site readings for specified sites within a time range"""
        return await count_site_readings_for_sites_and_time(
            session=session,
            site_ids=site_ids,
            start_time=start_time,
            end_time=end_time,
        )
