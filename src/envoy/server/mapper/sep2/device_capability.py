from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse

from envoy.server.mapper.common import generate_href
from envoy.server.request_state import RequestStateParameters


class DeviceCapabilityMapper:
    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, links: dict) -> DeviceCapabilityResponse:
        return DeviceCapabilityResponse.model_validate(
            {"href": generate_href(uri.DeviceCapabilityUri, rs_params), **links}
        )
