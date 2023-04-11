from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse


class DeviceCapabilityManager:
    @staticmethod
    async def fetch_device_capability() -> DeviceCapabilityResponse:
        return DeviceCapabilityMapper.map_to_response()
