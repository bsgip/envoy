from envoy.server.schema.sep2 import link, uri
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse


class DeviceCapabilityMapper:
    @staticmethod
    def map_to_response() -> DeviceCapabilityResponse:
        return DeviceCapabilityResponse.validate(
            {"href": uri.DeviceCapabilityUri, **link.get_supported_links(DeviceCapabilityResponse)}
        )
