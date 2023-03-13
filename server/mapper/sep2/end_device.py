from server.mapper.base import BaseMapper
from server.schema.sep2.end_device import EndDeviceResponse


class EndDeviceMapper(BaseMapper):
    _map = {
        "lfdi": "lFDI",
        "sfdi": "sFDI",
        "device_category": "deviceCategory",
        "changed_time": "changedTime",
    }

    @classmethod
    def map_to_response(cls, site_data):
        site_id = site_data.pop("site_id")
        return EndDeviceResponse(
            href=f"/edev/{site_id}", **cls._map_colnames(site_data), enabled=1
        )
