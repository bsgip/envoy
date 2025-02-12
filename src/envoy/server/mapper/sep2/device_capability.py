from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from envoy_schema.server.schema.sep2.identification import ListLink

from envoy.server.mapper.common import generate_href


class DeviceCapabilityMapper:
    @staticmethod
    def map_to_response(*, href_prefix: str, edev_cnt: int, mup_cnt: int) -> DeviceCapabilityResponse:
        """Maps inputs to generate a Response object.

        Args:
            href_prefix (str): this will prefix all href's in the response.
            edev_cnt (int): Count of EndDevice entities to include in link-list response.
            mup_cnt (int): Count of MirrorUsagePoint entities to include in link-list response.
        Return:
            DeviceCapabilityResponse
        """
        return DeviceCapabilityResponse(
            href=generate_href(uri.DeviceCapabilityUri, href_prefix),
            EndDeviceListLink=ListLink(href=generate_href(uri.EndDeviceListUri, href_prefix), all_=edev_cnt),
            MirrorUsagePointListLink=ListLink(
                href=generate_href(uri.MirrorUsagePointListUri, href_prefix), all_=mup_cnt
            ),
            # TimeLink
        )

    @staticmethod
    def map_to_unregistered_response(href_prefix: str) -> DeviceCapabilityResponse:
        """This is the most basic dcap that gets served if we have a client connecting that hasn't yet registered
        a site"""
        return DeviceCapabilityResponse.model_validate(
            {
                "href": generate_href(uri.DeviceCapabilityUri, href_prefix),
                "EndDeviceListLink": {
                    "href": generate_href(uri.EndDeviceListUri, href_prefix),
                },
            }
        )
