from envoy.server.crud import link
from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse


class DeviceCapabilityManager:
    @staticmethod
    async def fetch_device_capability(aggregator_id: int) -> DeviceCapabilityResponse:
        links = await link.get_supported_links(DeviceCapabilityResponse, aggregator_id)
        return DeviceCapabilityMapper.map_to_response(links)
