import pytest
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from envoy_schema.server.schema.sep2.identification import ListLink
from envoy_schema.server.schema.uri import DeviceCapabilityUri

from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope, SiteRequestScope


@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(DeviceOrAggregatorRequestScope, optional_is_none=True),
        generate_class_instance(DeviceOrAggregatorRequestScope, optional_is_none=False),
        generate_class_instance(SiteRequestScope, optional_is_none=True),
        generate_class_instance(SiteRequestScope, optional_is_none=False),
    ],
)
def test_map_to_response(scope: BaseRequestScope):
    links = {
        # "DemandResponseProgramListLink": {"all_": "1", "href": "/drp"},
        # "MessagingProgramListLink": {"all_": "2", "href": "/msg"},
        "EndDeviceListLink": {"all_": "1", "href": "/my/customer/uri"},
    }

    device_capability = DeviceCapabilityMapper.map_to_response(scope=scope, links=links)
    assert device_capability is not None
    assert isinstance(device_capability, DeviceCapabilityResponse)
    assert isinstance(device_capability.EndDeviceListLink, ListLink)

    assert device_capability.EndDeviceListLink == ListLink(href="/my/customer/uri", all_="1")

    if scope.href_prefix is None:
        assert device_capability.href == DeviceCapabilityUri
    else:
        assert device_capability.href == f"/{scope.href_prefix}{DeviceCapabilityUri}"


@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(DeviceOrAggregatorRequestScope, optional_is_none=True),
        generate_class_instance(DeviceOrAggregatorRequestScope, optional_is_none=False),
        generate_class_instance(SiteRequestScope, optional_is_none=True),
        generate_class_instance(SiteRequestScope, optional_is_none=False),
    ],
)
def test_map_to_unregistered_response(scope: BaseRequestScope):
    device_capability = DeviceCapabilityMapper.map_to_unregistered_response(scope=scope)
    assert device_capability is not None
    assert isinstance(device_capability, DeviceCapabilityResponse)
    assert isinstance(device_capability.EndDeviceListLink, ListLink)

    if scope.href_prefix is None:
        assert device_capability.href == DeviceCapabilityUri
        assert device_capability.EndDeviceListLink == ListLink(href="/edev")
    else:
        assert device_capability.EndDeviceListLink == ListLink(href="/" + scope.href_prefix + "/edev")
        assert device_capability.href == f"/{scope.href_prefix}{DeviceCapabilityUri}"
