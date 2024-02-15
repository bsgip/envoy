from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud import link
from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.request_state import RequestStateParameters


class DeviceCapabilityManager:
    @staticmethod
    async def fetch_device_capability(
        session: AsyncSession, request_params: RequestStateParameters
    ) -> DeviceCapabilityResponse:
        # Get all the 'Link's and 'ListLink's for a device capability response
        links = await link.get_supported_links(
            session=session,
            rs_params=request_params,
            model=DeviceCapabilityResponse,
        )

        return DeviceCapabilityMapper.map_to_response(rs_params=request_params, links=links)
