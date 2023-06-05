from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.end_device import (
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.mapper.csip_aus.connection_point import ConnectionPointMapper
from envoy.server.mapper.sep2.end_device import EndDeviceListMapper, EndDeviceMapper
from envoy.server.schema.csip_aus.connection_point import ConnectionPointResponse
from envoy.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse


class EndDeviceManager:
    @staticmethod
    async def fetch_enddevice_with_site_id(
        session: AsyncSession, site_id: int, aggregator_id: int
    ) -> Optional[EndDeviceResponse]:
        site = await select_single_site_with_site_id(session=session, site_id=site_id, aggregator_id=aggregator_id)
        if site is None:
            return None
        return EndDeviceMapper.map_to_response(site)

    @staticmethod
    async def add_or_update_enddevice_for_aggregator(
        session: AsyncSession, aggregator_id: int, end_device: EndDeviceRequest
    ) -> int:
        site = EndDeviceMapper.map_from_request(end_device, aggregator_id, datetime.now(tz=timezone.utc))
        result = await upsert_site_for_aggregator(session, aggregator_id, site)
        await session.commit()
        return result

    @staticmethod
    async def fetch_connection_point_for_site(
        session: AsyncSession, site_id: int, aggregator_id: int
    ) -> Optional[ConnectionPointResponse]:
        """Given a site ID and requesting aggregator. Fetch the connection point associated with a particular site"""
        site = await select_single_site_with_site_id(session=session, site_id=site_id, aggregator_id=aggregator_id)
        if site is None:
            return None
        return ConnectionPointMapper.map_to_response(site)

    @staticmethod
    async def update_nmi_for_site(session: AsyncSession, aggregator_id: int, site_id: int, nmi: Optional[str]) -> bool:
        """Attempts to update the NMI for a designated site. Returns True if the update proceeded successfully,
        False if the Site doesn't exist / belongs to another aggregator_id"""

        site = await select_single_site_with_site_id(session=session, site_id=site_id, aggregator_id=aggregator_id)
        if site is None:
            return False

        site.nmi = nmi
        site.changed_time = datetime.now(tz=timezone.utc)
        await session.commit()
        return True


class EndDeviceListManager:
    @staticmethod
    async def fetch_enddevicelist_with_aggregator_id(
        session: AsyncSession,
        aggregator_id: int,
        start: int,
        after: datetime,
        limit: int,
    ) -> EndDeviceListResponse:
        site_list = await select_all_sites_with_aggregator_id(session, aggregator_id, start, after, limit)
        site_count = await select_aggregator_site_count(session, aggregator_id, after)
        return EndDeviceListMapper.map_to_response(site_list, site_count)
