from datetime import datetime
from typing import Sequence

from envoy_schema.admin.schema.site_reading import AdminSiteReading, AdminSiteReadingPageResponse
from envoy.server.model.site_reading import SiteReading


class AdminSiteReadingMapper:
    """Mapper for converting between domain models and admin schema objects."""

    @staticmethod
    def map_to_admin_reading(site_reading: SiteReading) -> AdminSiteReading:
        """Convert a SiteReading model to AdminSiteReading schema"""
        reading_type = site_reading.site_reading_type

        return AdminSiteReading(
            # Reading data
            site_reading_id=site_reading.site_reading_id,
            site_id=reading_type.site_id,
            time_period_start=site_reading.time_period_start,
            time_period_seconds=site_reading.time_period_seconds,
            value=site_reading.value,
            local_id=site_reading.local_id,
            quality_flags=site_reading.quality_flags,
            reading_created_time=site_reading.created_time,
            reading_changed_time=site_reading.changed_time,
            # Reading type metadata
            site_reading_type_id=reading_type.site_reading_type_id,
            aggregator_id=reading_type.aggregator_id,
            uom=reading_type.uom,
            data_qualifier=reading_type.data_qualifier,
            flow_direction=reading_type.flow_direction,
            accumulation_behaviour=reading_type.accumulation_behaviour,
            kind=reading_type.kind,
            phase=reading_type.phase,
            power_of_ten_multiplier=reading_type.power_of_ten_multiplier,
            default_interval_seconds=reading_type.default_interval_seconds,
            role_flags=reading_type.role_flags,
            reading_type_created_time=reading_type.created_time,
            reading_type_changed_time=reading_type.changed_time,
        )

    @staticmethod
    def map_to_admin_reading_page_response(
        site_readings: Sequence[SiteReading],
        total_count: int,
        start: int,
        limit: int,
        site_ids: list[int],
        start_time: datetime,
        end_time: datetime,
    ) -> AdminSiteReadingPageResponse:
        """Convert a sequence of SiteReading models to AdminSiteReadingPageResponse.

        Args:
            site_readings: Sequence of SiteReading model instances
            total_count: Total number of readings matching the query (for pagination)
            start: Pagination offset used in the query
            limit: Pagination limit used in the query
            site_ids: Site IDs filter used in the query
            start_time: Start time filter used in the query
            end_time: End time filter used in the query

        Returns:
            AdminSiteReadingPageResponse with converted readings and pagination metadata
        """
        admin_readings = [AdminSiteReadingMapper.map_to_admin_reading(reading) for reading in site_readings]

        return AdminSiteReadingPageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            site_ids=site_ids,
            start_time=start_time,
            end_time=end_time,
            readings=admin_readings,
        )
