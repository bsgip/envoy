from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from envoy_schema.server.schema.sep2.identification import Link, ListLink

from envoy.server.mapper.common import generate_href
from envoy.server.request_scope import BaseRequestScope


class DeviceCapabilityMapper:
    @staticmethod
    def map_to_response(
        scope: BaseRequestScope, edev_cnt: int, mup_cnt: int, pollrate_seconds: int
    ) -> DeviceCapabilityResponse:
        """Maps inputs to generate a Response object.

        Args:
            href_prefix (str): this will prefix all href's in the response.
            edev_cnt (int): Count of EndDevice entities to include in link-list response.
            mup_cnt (int): Count of MirrorUsagePoint entities to include in link-list response.
        Return:
            DeviceCapabilityResponse
        """
        return DeviceCapabilityResponse(
            href=generate_href(uri.DeviceCapabilityUri, scope),
            pollRate=pollrate_seconds,
            EndDeviceListLink=ListLink(href=generate_href(uri.EndDeviceListUri, scope), all_=edev_cnt),
            MirrorUsagePointListLink=ListLink(href=generate_href(uri.MirrorUsagePointListUri, scope), all_=mup_cnt),
            TimeLink=Link(href=generate_href(uri.TimeUri, scope)),
        )

    @staticmethod
    def map_to_unregistered_response(scope: BaseRequestScope) -> DeviceCapabilityResponse:
        """This is the most basic dcap that gets served if we have a client connecting that hasn't yet registered
        a site"""
        return DeviceCapabilityResponse(
            href=generate_href(uri.DeviceCapabilityUri, scope),
            EndDeviceListLink=ListLink(
                href=generate_href(uri.EndDeviceListUri, scope), all_=0
            ),  # Unregistered so 0 edevs in list
            MirrorUsagePointListLink=ListLink(
                href=generate_href(uri.MirrorUsagePointListUri, scope),
                all_=0,  # mup requires edev (referenced via non-optional deviceLFDI), so must be 0 here
            ),
            TimeLink=Link(href=generate_href(uri.TimeUri, scope)),
        )
