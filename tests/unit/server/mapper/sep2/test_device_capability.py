from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from envoy_schema.server.schema.sep2.identification import ListLink

from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.request_state import RequestStateParameters


def test_map_to_response():
    links = {
        # "DemandResponseProgramListLink": {"all_": "1", "href": "/drp"},
        # "MessagingProgramListLink": {"all_": "2", "href": "/msg"},
        "EndDeviceListLink": {"all_": "1", "href": "/edev"},
    }

    device_capability = DeviceCapabilityMapper.map_to_response(
        rs_params=RequestStateParameters(1, None, None), links=links
    )
    assert device_capability is not None
    assert isinstance(device_capability, DeviceCapabilityResponse)
    # assert isinstance(device_capability.DemandResponseProgramListLink, ListLink)
    # assert device_capability.DemandResponseProgramListLink == ListLink(href="/drp", all_="1")
    # assert isinstance(device_capability.MessagingProgramListLink, ListLink)
    # assert device_capability.MessagingProgramListLink == ListLink(href="/msg", all_="2")
    assert isinstance(device_capability.EndDeviceListLink, ListLink)
    assert device_capability.EndDeviceListLink == ListLink(href="/edev", all_="1")
