import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from envoy_schema.server.schema.sep2.types import UomType
from envoy.admin.crud.site import select_single_site_no_scoping
from envoy.admin.crud.site_reading import (
    count_site_readings_for_site_and_time,
    select_csip_aus_site_type_ids,
    select_site_readings_for_site_and_time,
)
from envoy.admin.mapper.site_reading import AdminSiteReadingMapper
from envoy_schema.admin.schema.site_reading import CSIPAusSiteReadingUnit, CSIPAusSiteReadingPageResponse

from envoy.server.model.site import Site


class AdminSiteReadingManager:
    """Logic layer for admin site reading operations."""

    @staticmethod
    async def get_site_readings_for_site_and_time(
        session: AsyncSession,
        site_id: int,
        csip_unit: CSIPAusSiteReadingUnit,
        start_time: datetime,
        end_time: datetime,
        start: int = 0,
        limit: int = 500,
    ) -> CSIPAusSiteReadingPageResponse:
        """Get site readings for specified site within a time range."""

        # Convert CSIP unit to UOM for database query
        uom: UomType = AdminSiteReadingMapper.csip_unit_to_uom(csip_unit)

        # Query 1: get the aggregator id from site to help hit the index of SiteReadingType
        site: Optional[Site] = await select_single_site_no_scoping(session=session, site_id=site_id)

        empty_return = AdminSiteReadingMapper.map_to_csip_aus_reading_page_response(
            site_readings=[],
            total_count=0,
            start=start,
            limit=limit,
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            requested_unit=csip_unit,
        )

        if not site:
            return empty_return

        # Query 2: retrieve the reading type IDs for this site in order to hit index of SiteReading
        site_type_ids = await select_csip_aus_site_type_ids(
            session=session, aggregator_id=site.aggregator_id, site_id=site_id, uom=uom
        )

        if not site_type_ids:
            return empty_return

        # Queries 3: Get total count and readings in parallel
        total_count_task = count_site_readings_for_site_and_time(
            session=session,
            site_type_ids=site_type_ids,
            start_time=start_time,
            end_time=end_time,
        )

        site_readings_task = select_site_readings_for_site_and_time(
            session=session,
            site_type_ids=site_type_ids,
            start_time=start_time,
            end_time=end_time,
            start=start,
            limit=limit,
        )

        total_count, site_readings = await asyncio.gather(total_count_task, site_readings_task)

        return AdminSiteReadingMapper.map_to_csip_aus_reading_page_response(
            site_readings=site_readings,
            total_count=total_count,
            start=start,
            limit=limit,
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            requested_unit=csip_unit,
        )
