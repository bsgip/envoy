from datetime import datetime
from typing import Sequence

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from envoy_schema.server.schema.sep2.types import DEVICE_CATEGORY_ALL_SET, DeviceCategory

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href
from envoy.server.model.site import Site
from envoy.server.request_state import RequestStateParameters
from envoy.server.settings import settings


class EndDeviceMapper:
    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, site: Site) -> EndDeviceResponse:
        edev_href = generate_href(uri.EndDeviceUri, rs_params, site_id=site.site_id)
        return EndDeviceResponse.model_validate(
            {
                "href": edev_href,
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "deviceCategory": f"{site.device_category:x}",  # deviceCategory is a hex string
                "changedTime": int(site.changed_time.timestamp()),
                "enabled": True,
                "ConnectionPointLink": ConnectionPointLink(href=edev_href + "/cp"),
            }
        )

    @staticmethod
    def map_from_request(end_device: EndDeviceRequest, aggregator_id: int, changed_time: datetime) -> Site:
        # deviceCategory is a hex string
        device_category: DeviceCategory
        if end_device.deviceCategory:
            raw_dc = int(end_device.deviceCategory, 16)
            if raw_dc > DEVICE_CATEGORY_ALL_SET or raw_dc < 0:
                raise InvalidMappingError(
                    f"deviceCategory: {end_device.deviceCategory} int({raw_dc}) doesn't map to a known DeviceCategory"
                )
            device_category = DeviceCategory(raw_dc)
        else:
            device_category = DeviceCategory(0)

        return Site(
            lfdi=end_device.lFDI,
            sfdi=end_device.sFDI,
            changed_time=changed_time,
            aggregator_id=aggregator_id,
            device_category=device_category,
            timezone_id=settings.default_timezone,
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
                "EndDevice": [EndDeviceMapper.map_to_response(rs_params, site) for site in site_list],
            }
        )
