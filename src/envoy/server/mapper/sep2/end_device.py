from datetime import datetime

from envoy.server.model.site import Site
from envoy.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy.server.schema.sep2.end_device import (
    DeviceCategory,
    EndDeviceListResponse,
    EndDeviceRequest,
    EndDeviceResponse,
)


class EndDeviceMapper:
    @staticmethod
    def map_to_response(site: Site) -> EndDeviceResponse:
        edev_href = f"/edev/{site.site_id}"
        return EndDeviceResponse.validate(
            {
                "href": edev_href,
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "deviceCategory": f"{site.device_category:x}",  # deviceCategory is a hex string
                "changedTime": int(site.changed_time.timestamp()),
                "enabled": True,
                "ConnectionPointLink": ConnectionPointLink(href=edev_href + "/cp")
            }
        )

    @staticmethod
    def map_from_request(
        end_device: EndDeviceRequest, aggregator_id: int, changed_time: datetime
    ) -> Site:
        # deviceCategory is a hex string
        device_category: DeviceCategory
        if end_device.deviceCategory:
            device_category = DeviceCategory(int(end_device.deviceCategory, 16))
        else:
            device_category = DeviceCategory(0)

        return Site(
            lfdi=end_device.lFDI,
            sfdi=end_device.sFDI,
            changed_time=changed_time,
            aggregator_id=aggregator_id,
            device_category=device_category
        )


class EndDeviceListMapper:
    @staticmethod
    def map_to_response(
        site_list: list[Site], site_count: int
    ) -> EndDeviceListResponse:
        return EndDeviceListResponse.validate(
            {
                "href": "/edev",
                "all_": site_count,
                "result": len(site_list),
                "EndDevice": [
                    EndDeviceMapper.map_to_response(site) for site in site_list
                ],
            }
        )
