from envoy.server.schema import uri
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse


class DeviceCapabilityMapper:
    @staticmethod
    def map_to_response(links: dict) -> DeviceCapabilityResponse:
        return DeviceCapabilityResponse.validate({"href": uri.DeviceCapabilityUri, **links})
