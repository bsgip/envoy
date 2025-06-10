from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.site_reading import count_site_readings_for_site_and_time, select_site_readings_for_site_and_time
from envoy.admin.mapper.site_reading import AdminSiteReadingMapper
from envoy_schema.admin.schema.site_reading import AdminSiteReadingPageResponse


class AdminSiteReadingManager:
    """Logic layer for admin site reading operations."""

    @staticmethod
    async def get_site_readings_for_site_and_time(
        session: AsyncSession,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        start: int = 0,
        limit: int = 1000,
    ) -> AdminSiteReadingPageResponse:
        """Get site readings for specified site within a time range."""

        # Get total count for pagination metadata
        total_count = await count_site_readings_for_site_and_time(
            session=session,
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Get the actual readings
        site_readings = await select_site_readings_for_site_and_time(
            session=session,
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            start=start,
            limit=limit,
        )

        return AdminSiteReadingMapper.map_to_admin_reading_page_response(
            site_readings=site_readings,
            total_count=total_count,
            start=start,
            limit=limit,
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )
