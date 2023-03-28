from datetime import datetime

from envoy.server.model.site import Site
from envoy.server.schema.sep2.end_device import (
    EndDeviceListResponse,
    EndDeviceRequest,
    EndDeviceResponse,
)


class EndDeviceMapper:
    @staticmethod
    def map_to_response(site: Site) -> EndDeviceResponse:
        return EndDeviceResponse.validate(
            {
                "href": f"/edev/{site.site_id}",
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "deviceCategory": site.device_category,
                "changedTime": int(site.changed_time.timestamp()),
                "enabled": True,
            }
        )

    @staticmethod
    def map_from_request(
        end_device: EndDeviceRequest, aggregator_id: int, changed_time: datetime
    ) -> Site:
        return Site(
            lfdi=end_device.lFDI,
            sfdi=end_device.sFDI,
            changed_time=changed_time,
            device_category=end_device.deviceCategory,
            aggregator_id=aggregator_id,
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
