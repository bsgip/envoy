from server.schema.sep2.end_device import EndDeviceResponse, EndDeviceListResponse
from server.model.site import Site


class EndDeviceMapper:
    @staticmethod
    def map_to_response(site: Site) -> EndDeviceResponse:
        return EndDeviceResponse.validate(
            {
                "href": f"/edev/{site.site_id}",
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "deviceCategory": site.device_category,
                "changedTime": site.changed_time,
                "enabled": True,
            }
        )


class EndDeviceListMapper:
    @staticmethod
    def map_to_response(site_list: list[Site]) -> EndDeviceListResponse:
        return EndDeviceListResponse.validate(
            [
                {
                    "href": f"/edev/{site.site_id}",
                    "lFDI": site.lfdi,
                    "sFDI": site.sfdi,
                    "deviceCategory": site.device_category,
                    "changedTime": site.changed_time,
                    "enabled": True,
                }
                for site in site_list
            ]
        )
