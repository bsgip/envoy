import unittest.mock as mock
from datetime import datetime
from typing import Optional

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance, generate_value
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.end_device import (
    EndDeviceListResponse,
    EndDeviceRequest,
    EndDeviceResponse,
    RegistrationResponse,
)
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.types import DEVICE_CATEGORY_ALL_SET, DeviceCategory

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.sep2.end_device import (
    EndDeviceListMapper,
    EndDeviceMapper,
    RegistrationMapper,
    VirtualEndDeviceMapper,
)
from envoy.server.model.site import Site
from envoy.server.request_scope import BaseRequestScope


def test_device_category_round_trip():
    """Tests that the mapping for device_category from int to hex string works both ways"""

    for dc in [DEVICE_CATEGORY_ALL_SET] + [x for x in DeviceCategory]:
        site: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
        site.device_category = dc
        scope: BaseRequestScope = generate_class_instance(BaseRequestScope)

        end_device = EndDeviceMapper.map_to_response(scope, site)

        roundtrip_site = EndDeviceMapper.map_from_request(end_device, 1, datetime.now(), 2)
        assert roundtrip_site.device_category == site.device_category


def test_map_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    site_all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    site_optional: Site = generate_class_instance(Site, seed=202, optional_is_none=True)
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope)

    result_all_set = EndDeviceMapper.map_to_response(scope, site_all_set)
    assert result_all_set is not None
    assert isinstance(result_all_set, EndDeviceResponse)
    assert result_all_set.changedTime == site_all_set.changed_time.timestamp()
    assert result_all_set.lFDI == site_all_set.lfdi
    assert result_all_set.deviceCategory == hex(site_all_set.device_category)[2:], "Expected hex string with no 0x"
    assert isinstance(result_all_set.ConnectionPointLink, ConnectionPointLink)
    assert isinstance(result_all_set.DERListLink, ListLink)
    assert isinstance(result_all_set.SubscriptionListLink, ListLink)
    assert isinstance(result_all_set.RegistrationLink, Link)

    # Validate the links are unique and all extend the edev base href
    all_child_hrefs = [
        result_all_set.ConnectionPointLink.href,
        result_all_set.DERListLink.href,
        result_all_set.SubscriptionListLink.href,
        result_all_set.RegistrationLink.href,
    ]
    assert len(all_child_hrefs) == len(set(all_child_hrefs)), f"Expected unique hrefs for {all_child_hrefs}"
    for child_href in all_child_hrefs:
        assert child_href != result_all_set.href, "Children must NOT match base href"
        assert child_href.startswith(result_all_set.href), "Children must extend base href"

    result_optional = EndDeviceMapper.map_to_response(scope, site_optional)
    assert result_optional is not None
    assert isinstance(result_optional, EndDeviceResponse)
    assert result_optional.changedTime == site_optional.changed_time.timestamp()
    assert result_optional.lFDI == site_optional.lfdi
    assert result_optional.deviceCategory == hex(site_optional.device_category)[2:], "Expected hex string with no 0x"
    assert isinstance(result_optional.ConnectionPointLink, ConnectionPointLink)
    assert isinstance(result_optional.DERListLink, ListLink)
    assert isinstance(result_optional.SubscriptionListLink, ListLink)
    assert isinstance(result_optional.RegistrationLink, Link)

    # Validate the links are unique and all extend the edev base href
    all_child_hrefs = [
        result_optional.ConnectionPointLink.href,
        result_optional.DERListLink.href,
        result_optional.SubscriptionListLink.href,
        result_optional.RegistrationLink.href,
    ]
    assert len(all_child_hrefs) == len(set(all_child_hrefs)), f"Expected unique hrefs for {all_child_hrefs}"
    for child_href in all_child_hrefs:
        assert child_href != result_optional.href, "Children must NOT match base href"
        assert child_href.startswith(result_optional.href), "Children must extend base href"


def test_list_map_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    site1: Site = generate_class_instance(Site, seed=303, optional_is_none=False, generate_relationships=False)
    site2: Site = generate_class_instance(Site, seed=404, optional_is_none=False, generate_relationships=True)
    site3: Site = generate_class_instance(Site, seed=505, optional_is_none=True, generate_relationships=False)
    site4: Site = generate_class_instance(Site, seed=606, optional_is_none=True, generate_relationships=True)
    site_count = 199
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope)

    all_sites = [site1, site2, site3, site4]

    result = EndDeviceListMapper.map_to_response(scope, all_sites, site_count)
    assert result is not None
    assert isinstance(result, EndDeviceListResponse)
    assert result.all_ == site_count
    assert result.results == len(all_sites)
    assert_list_type(EndDeviceResponse, result.EndDevice, len(all_sites))
    assert len(set([ed.lFDI for ed in result.EndDevice])) == len(
        all_sites
    ), f"Expected {len(all_sites)} unique LFDI's in the children"

    empty_result = EndDeviceListMapper.map_to_response(scope, [], site_count)
    assert empty_result is not None
    assert isinstance(empty_result, EndDeviceListResponse)
    assert empty_result.all_ == site_count
    assert_list_type(EndDeviceResponse, empty_result.EndDevice, 0)

    no_result = EndDeviceListMapper.map_to_response(scope, [], 0)
    assert no_result is not None
    assert isinstance(no_result, EndDeviceListResponse)
    assert no_result.all_ == 0
    assert_list_type(EndDeviceResponse, no_result.EndDevice, 0)


@mock.patch("envoy.server.mapper.sep2.end_device.settings")
def test_map_from_request(mock_settings: mock.MagicMock):
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    mock_settings.default_timezone = "abc/123"

    end_device_all_set: EndDeviceRequest = generate_class_instance(EndDeviceRequest, seed=101, optional_is_none=False)
    end_device_all_set.deviceCategory = "c0ffee"  # needs to be a hex string
    end_device_optional: EndDeviceRequest = generate_class_instance(EndDeviceRequest, seed=202, optional_is_none=True)
    end_device_optional.deviceCategory = None
    changed_time: datetime = generate_value(datetime, 303)
    aggregator_id: int = 404
    registration_pin: int = 505

    result_all_set = EndDeviceMapper.map_from_request(end_device_all_set, aggregator_id, changed_time, registration_pin)
    assert result_all_set is not None
    assert isinstance(result_all_set, Site)
    assert result_all_set.changed_time == changed_time
    assert result_all_set.aggregator_id == aggregator_id
    assert result_all_set.lfdi == end_device_all_set.lFDI
    assert isinstance(result_all_set.device_category, DeviceCategory)
    assert result_all_set.device_category == int("c0ffee", 16)
    assert result_all_set.timezone_id == "abc/123"
    assert result_all_set.registration_pin == registration_pin

    result_optional = EndDeviceMapper.map_from_request(
        end_device_optional, aggregator_id, changed_time, registration_pin
    )
    assert result_optional is not None
    assert isinstance(result_optional, Site)
    assert result_optional.changed_time == changed_time
    assert result_optional.aggregator_id == aggregator_id
    assert result_optional.lfdi == end_device_optional.lFDI
    assert isinstance(result_all_set.device_category, DeviceCategory)
    assert result_optional.device_category == DeviceCategory(0)
    assert result_optional.timezone_id == "abc/123"
    assert result_optional.registration_pin == registration_pin


def test_map_from_request_invalid_device_category():
    """Asserts that invalid device category values raise appropriate exceptions"""
    dc_too_big: EndDeviceRequest = generate_class_instance(EndDeviceRequest, seed=101)
    too_big_dc = int(DEVICE_CATEGORY_ALL_SET) + 1
    dc_too_big.deviceCategory = f"{too_big_dc:x}"

    dc_negative: EndDeviceRequest = generate_class_instance(EndDeviceRequest, seed=202)
    dc_negative.deviceCategory = f"{-1:x}"

    with pytest.raises(InvalidMappingError):
        EndDeviceMapper.map_from_request(dc_too_big, 1, datetime.now(), 2)

    with pytest.raises(InvalidMappingError):
        EndDeviceMapper.map_from_request(dc_negative, 1, datetime.now(), 2)


def test_virtual_end_device_map_to_response():
    """Simple sanity check on the virtual end device mapper to ensure things don't break with a variety of values."""
    site_all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    site_optional: Site = generate_class_instance(Site, seed=202, optional_is_none=True)
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope)

    result_all_set = VirtualEndDeviceMapper.map_to_response(scope, site_all_set)
    assert result_all_set is not None
    assert isinstance(result_all_set, EndDeviceResponse)
    assert result_all_set.changedTime == site_all_set.changed_time.timestamp()
    assert result_all_set.lFDI == site_all_set.lfdi
    assert result_all_set.deviceCategory == hex(site_all_set.device_category)[2:], "Expected hex string with no 0x"

    result_optional = EndDeviceMapper.map_to_response(scope, site_optional)
    assert result_optional is not None
    assert isinstance(result_optional, EndDeviceResponse)
    assert result_optional.changedTime == site_optional.changed_time.timestamp()
    assert result_optional.lFDI == site_optional.lfdi
    assert result_optional.deviceCategory == hex(site_optional.device_category)[2:], "Expected hex string with no 0x"


@pytest.mark.parametrize(
    "pin, expected",
    [
        (0, 0),
        (1, 11),
        (98, 987),
        (100, 1001),
        (444, 4442),
        (44400, 444002),
        (10203, 102036),
        (12345, 123455),  # From the example in sep2
        (99999, 999995),
    ],
)
def test_add_checksum_to_registration_pin(pin, expected):
    """Various simple test cases"""
    actual = RegistrationMapper.add_checksum_to_registration_pin(pin)
    assert actual == expected


@pytest.mark.parametrize("href_prefix", [None, "/foo/bar"])
def test_RegistrationMapper_map_to_response(href_prefix: Optional[str]):
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    site_all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    site_optional: Site = generate_class_instance(Site, seed=202, optional_is_none=True)
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope, href_prefix=href_prefix)

    result_all_set = RegistrationMapper.map_to_response(scope, site_all_set)
    assert result_all_set is not None
    assert isinstance(result_all_set, RegistrationResponse)
    if scope.href_prefix is not None:
        assert result_all_set.href.startswith(scope.href_prefix)
    assert result_all_set.dateTimeRegistered == site_all_set.created_time.timestamp()
    assert result_all_set.pIN == RegistrationMapper.add_checksum_to_registration_pin(site_all_set.registration_pin)

    result_optional = RegistrationMapper.map_to_response(scope, site_optional)
    assert result_optional is not None
    assert isinstance(result_optional, RegistrationResponse)
    if scope.href_prefix is not None:
        assert result_optional.href.startswith(scope.href_prefix)
    assert result_optional.dateTimeRegistered == site_optional.created_time.timestamp()
    assert result_optional.pIN == RegistrationMapper.add_checksum_to_registration_pin(site_optional.registration_pin)
