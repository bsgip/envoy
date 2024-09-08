from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse

from envoy.server.mapper.common import generate_href
from envoy.server.request_scope import BaseRequestScope


class DeviceCapabilityMapper:
    @staticmethod
    def map_to_response(scope: BaseRequestScope, links: dict) -> DeviceCapabilityResponse:
        return DeviceCapabilityResponse.model_validate({"href": generate_href(uri.DeviceCapabilityUri, scope), **links})

    @staticmethod
    def map_to_unregistered_response(scope: BaseRequestScope) -> DeviceCapabilityResponse:
        """This is the most basic dcap that gets served if we have a client connecting that hasn't yet registered
        a site"""
        return DeviceCapabilityResponse.model_validate(
            {
                "href": generate_href(uri.DeviceCapabilityUri, scope),
                "EndDeviceListLink": {
                    "href": generate_href(uri.EndDeviceListUri, scope),
                },
            }
        )
