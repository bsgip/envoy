from sqlalchemy.ext.asyncio import AsyncSession

from server.crud.end_device import (
    select_all_sites_with_aggregator_id,
    select_single_site_with_site_id,
)
from server.mapper.sep2.end_device import EndDeviceMapper, EndDeviceListMapper
from server.schema.sep2.end_device import EndDeviceResponse, EndDeviceListResponse


class EndDeviceManager:
    @staticmethod
    async def fetch_enddevice_with_site_id(
        session: AsyncSession, site_id: int, aggregator_id: int
    ) -> EndDeviceResponse:
        site = select_single_site_with_site_id(
            session=session, site_id=site_id, aggregator_id=aggregator_id
        )
        return EndDeviceMapper.map_to_response(site)


class EndDeviceListManager:
    @staticmethod
    async def return_enddevice_with_site_id(
        session: AsyncSession, site_id: int, aggregator_id: int
    ) -> EndDeviceResponse:
        site_list = select_all_sites_with_aggregator_id(
            session=session, site_id=site_id, aggregator_id=aggregator_id
        )
        return EndDeviceListMapper.map_to_response(site_list)
