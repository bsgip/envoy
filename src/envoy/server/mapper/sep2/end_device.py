from datetime import datetime
from typing import Sequence

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from envoy_schema.server.schema.sep2.identification import ListLink
from envoy_schema.server.schema.sep2.types import SubscribableType

from envoy.server.mapper.common import generate_href, parse_device_category
from envoy.server.model.site import Site
from envoy.server.request_state import RequestStateParameters
from envoy.server.settings import settings


class EndDeviceMapper:
    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, site: Site) -> EndDeviceResponse:
        edev_href = generate_href(uri.EndDeviceUri, rs_params, site_id=site.site_id)
        fsa_href = generate_href(uri.FunctionSetAssignmentsListUri, rs_params, site_id=site.site_id)
        return EndDeviceResponse.model_validate(
            {
                "href": edev_href,
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "deviceCategory": f"{site.device_category:x}",  # deviceCategory is a hex string
                "changedTime": int(site.changed_time.timestamp()),
                "enabled": True,
                "ConnectionPointLink": ConnectionPointLink(href=edev_href + "/cp"),
                "FunctionSetAssignmentsListLink": ListLink(href=fsa_href),
            }
        )

    @staticmethod
    def map_from_request(end_device: EndDeviceRequest, aggregator_id: int, changed_time: datetime) -> Site:
        return Site(
            lfdi=end_device.lFDI,
            sfdi=end_device.sFDI,
            changed_time=changed_time,
            aggregator_id=aggregator_id,
            device_category=parse_device_category(end_device.deviceCategory),
            timezone_id=settings.default_timezone,
        )


class VirtualEndDeviceMapper:
    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, site: Site) -> EndDeviceResponse:
        edev_href = generate_href(uri.EndDeviceUri, rs_params, site_id=site.site_id)
        return EndDeviceResponse.model_validate(
            {
                "href": edev_href,
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "subscribable": SubscribableType.resource_does_not_support_subscriptions,
                "deviceCategory": f"{site.device_category:x}",  # deviceCategory is a hex string
                "changedTime": int(site.changed_time.timestamp()),
                "enabled": True,
            }
        )


class EndDeviceListMapper:
    @staticmethod
    def map_to_response(
        rs_params: RequestStateParameters, site_list: Sequence[Site], site_count: int
    ) -> EndDeviceListResponse:
        return EndDeviceListResponse.model_validate(
            {
                "href": generate_href(uri.EndDeviceListUri, rs_params),
                "all_": site_count,
                "results": len(site_list),
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "EndDevice": [EndDeviceMapper.map_to_response(rs_params, site) for site in site_list],
            }
        )
