from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse


class DeviceCapabilityMapper:
    @staticmethod
    def map_to_response(links: dict) -> DeviceCapabilityResponse:
        return DeviceCapabilityResponse.validate({"href": uri.DeviceCapabilityUri, **links})
