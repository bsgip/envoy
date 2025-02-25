from pathlib import Path

import pytest
from assertical.fake.generator import generate_class_instance


from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from envoy_schema.server.schema.sep2.identification import ListLink, Link
from envoy_schema.server.schema.uri import DeviceCapabilityUri, MirrorUsagePointListUri, TimeUri, EndDeviceListUri

from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope, SiteRequestScope


def _form_href(href_prefix: str | None, uri: str) -> str:
    return str(Path("/") / Path(href_prefix or "") / uri.lstrip("/"))


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

    edev_cnt = 1
    mup_cnt = 1

    device_capability = DeviceCapabilityMapper.map_to_response(scope=scope, edev_cnt=edev_cnt, mup_cnt=mup_cnt)
    assert device_capability is not None
    assert isinstance(device_capability, DeviceCapabilityResponse)

    assert device_capability.TimeLink == Link(href=_form_href(scope.href_prefix, TimeUri))
    assert device_capability.EndDeviceListLink == ListLink(
        href=_form_href(scope.href_prefix, EndDeviceListUri), all_=f"{edev_cnt}"
    )
    assert device_capability.MirrorUsagePointListLink == ListLink(
        href=_form_href(scope.href_prefix, MirrorUsagePointListUri), all_=f"{mup_cnt}"
    )
    assert device_capability.href == _form_href(scope.href_prefix, DeviceCapabilityUri)


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

    assert device_capability.href == _form_href(scope.href_prefix, DeviceCapabilityUri)
    assert device_capability.EndDeviceListLink == ListLink(href=_form_href(scope.href_prefix, EndDeviceListUri), all_=0)
