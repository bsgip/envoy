from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud import link
from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse


class DeviceCapabilityManager:
    @staticmethod
    async def fetch_device_capability(session: AsyncSession, aggregator_id: int) -> DeviceCapabilityResponse:
        # Get all the 'Link's and 'ListLink's for a device capability response
        links = await link.get_supported_links(
            session=session, model=DeviceCapabilityResponse, aggregator_id=aggregator_id
        )

        return DeviceCapabilityMapper.map_to_response(links=links)
