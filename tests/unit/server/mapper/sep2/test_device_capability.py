from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.schema.sep2.base import Link, ListLink
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse


def test_map_to_response():
    links = {
        "DemandResponseProgramListLink": {"all_": "1", "href": "/drp"},
        "MessagingProgramListLink": {"all_": "2", "href": "/msg"},
        "EndDeviceListLink": {"all_": "1", "href": "/edev"},
        "SelfDeviceLink": {"href": "/sdev"},
    }

    device_capability = DeviceCapabilityMapper.map_to_response(links=links)
    assert device_capability is not None
    assert isinstance(device_capability, DeviceCapabilityResponse)
    assert isinstance(device_capability.DemandResponseProgramListLink, ListLink)
    assert device_capability.DemandResponseProgramListLink == ListLink(href="/drp", all_="1")
    assert isinstance(device_capability.MessagingProgramListLink, ListLink)
    assert device_capability.MessagingProgramListLink == ListLink(href="/msg", all_="2")
    assert isinstance(device_capability.EndDeviceListLink, ListLink)
    assert device_capability.EndDeviceListLink == ListLink(href="/edev", all_="1")
    assert isinstance(device_capability.SelfDeviceLink, Link)
    assert device_capability.SelfDeviceLink == Link(href="/sdev")
