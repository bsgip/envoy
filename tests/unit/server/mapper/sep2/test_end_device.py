from envoy.server.mapper.sep2.end_device import EndDeviceMapper
from envoy.server.model.site import Site
from envoy.server.schema.sep2.end_device import EndDeviceResponse


def test_map_to_response():
    site: Site = None
    result: EndDeviceResponse = EndDeviceMapper.map_to_response(site)
    raise Exception('Not implemented')
