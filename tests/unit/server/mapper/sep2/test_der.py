from datetime import datetime
from typing import Any

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal
from assertical.fake.generator import enumerate_class_properties, generate_class_instance
from envoy_schema.server.schema.sep2.der import (
    DER,
    AlarmStatusType,
    ConnectStatusType,
    DERAvailability,
    DERCapability,
    DERControlType,
    DERListResponse,
    DERSettings,
    DERStatus,
    DOESupportedMode,
)
from envoy_schema.server.schema.sep2.identification import Link

from envoy.server.mapper.sep2.der import (
    DERAvailabilityMapper,
    DERCapabilityMapper,
    DERMapper,
    DERSettingMapper,
    DERStatusMapper,
    to_hex_binary,
)
from envoy.server.model.site import SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope


def assert_der_info_type_equal(t: type, expected: Any, actual: Any):
    """assert_class_instance_equality will only compare the "simple" types. It won't do a proper check on the
    ActivePower, ApparentPower (etc) types. This function does a deeper inspection"""

    ignored_props = {"href", "readingTime", "subscribable", "type", "updatedTime"}

    # Check the basic properties
    assert_class_instance_equality(
        t,
        expected,
        actual,
        ignored_properties=ignored_props,
    )

    # Check the various "complex" types of ActivePower/ApparentPower etc
    for prop in enumerate_class_properties(t):
        if prop.name in ignored_props:
            continue
        expected_value = getattr(expected, prop.name, None)
        actual_value = getattr(actual, prop.name, None)
        assert expected_value == actual_value, f"Property '{prop.name}'"


def test_der_mapping():
    all_set: SiteDER = generate_class_instance(SiteDER, seed=101, optional_is_none=False, generate_relationships=True)
    with_none: SiteDER = generate_class_instance(SiteDER, seed=202, optional_is_none=True, generate_relationships=True)

    scope = BaseRequestScope("lfdi", 111, "/my/prefix", 222)
    derp_id = 124124

    mapped_all_set = DERMapper.map_to_response(scope, all_set, derp_id)
    assert isinstance(mapped_all_set, DER)

    assert mapped_all_set.href.startswith("/my/prefix")
    assert str(all_set.site_id) in mapped_all_set.href
    assert isinstance(mapped_all_set.AssociatedDERProgramListLink, Link)
    assert isinstance(mapped_all_set.CurrentDERProgramLink, Link)
    assert isinstance(mapped_all_set.DERAvailabilityLink, Link)
    assert isinstance(mapped_all_set.DERCapabilityLink, Link)
    assert isinstance(mapped_all_set.DERSettingsLink, Link)
    assert isinstance(mapped_all_set.DERStatusLink, Link)
    assert f"/{derp_id}" in mapped_all_set.CurrentDERProgramLink.href
    assert str(all_set.site_id) in mapped_all_set.CurrentDERProgramLink.href

    # Test with NO active der program id
    mapped_all_set_no_actderp = DERMapper.map_to_response(scope, all_set, None)
    assert isinstance(mapped_all_set_no_actderp, DER)
    assert mapped_all_set_no_actderp.href.startswith("/my/prefix")
    assert str(all_set.site_id) in mapped_all_set_no_actderp.href
    assert mapped_all_set_no_actderp.CurrentDERProgramLink is None

    mapped_with_none = DERMapper.map_to_response(scope, with_none, derp_id)
    assert isinstance(mapped_with_none, DER)
    assert mapped_with_none.href.startswith("/my/prefix")
    assert str(with_none.site_id) in mapped_with_none.href
    assert isinstance(mapped_with_none.AssociatedDERProgramListLink, Link)
    assert isinstance(mapped_with_none.CurrentDERProgramLink, Link)
    assert isinstance(mapped_with_none.DERAvailabilityLink, Link)
    assert isinstance(mapped_with_none.DERCapabilityLink, Link)
    assert isinstance(mapped_with_none.DERSettingsLink, Link)
    assert isinstance(mapped_with_none.DERStatusLink, Link)
    assert f"/{derp_id}" in mapped_with_none.CurrentDERProgramLink.href
    assert str(with_none.site_id) in mapped_with_none.CurrentDERProgramLink.href


def test_der_list():
    ders: list[SiteDER] = [
        generate_class_instance(SiteDER, seed=101, optional_is_none=False, generate_relationships=True),
        generate_class_instance(SiteDER, seed=202, optional_is_none=True, generate_relationships=True),
    ]

    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope, site_id=11)
    poll_rate = 99
    count = 42

    mapped = DERMapper.map_to_list_response(scope, ders, count, poll_rate)
    assert isinstance(mapped, DERListResponse)
    assert mapped.results == 2
    assert mapped.all_ == count
    assert mapped.pollRate == poll_rate
    assert len(mapped.DER_) == len(ders)
    assert all([isinstance(x, DER) for x in mapped.DER_])


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_avail_roundtrip(optional_is_none: bool):
    """Tests that DERAvailability mapping is reversible"""
    expected: DERAvailability = generate_class_instance(
        DERAvailability, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, site_id=9876, href_prefix="/my/prefix"
    )
    entity_site_id = scope.site_id + 17
    changed_time = datetime(2023, 8, 9, 1, 2, 3)

    mapped = DERAvailabilityMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERAvailability)
    assert mapped.changed_time == changed_time

    actual = DERAvailabilityMapper.map_to_response(scope, mapped, entity_site_id)
    assert isinstance(actual, DERAvailability)

    assert_der_info_type_equal(DERAvailability, expected, actual)
    assert actual.href.startswith("/my/prefix")
    assert f"/{entity_site_id}" in actual.href
    assert f"/{scope.display_site_id}" not in actual.href, "Should be using the entity site ID in the href"
    assert f"/{scope.site_id}" not in actual.href, "Should be using the entity site ID in the href"
    assert_datetime_equal(changed_time, actual.readingTime)


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_status_roundtrip(optional_is_none: bool):
    """Tests that DERStatus mapping is reversible"""
    expected: DERStatus = generate_class_instance(
        DERStatus, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    if not optional_is_none:
        expected.alarmStatus = to_hex_binary(
            AlarmStatusType.DER_FAULT_EMERGENCY_LOCAL | AlarmStatusType.DER_FAULT_OVER_FREQUENCY
        )
        expected.manufacturerStatus.value = "lilval"
        if expected.genConnectStatus:
            expected.genConnectStatus.value = to_hex_binary(ConnectStatusType.CONNECTED | ConnectStatusType.AVAILABLE)
        if expected.storConnectStatus:
            expected.storConnectStatus.value = to_hex_binary(
                ConnectStatusType.OPERATING | ConnectStatusType.FAULT_ERROR
            )

    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, site_id=9875, href_prefix="/my/prefix"
    )
    entity_site_id = scope.site_id + 17
    changed_time = datetime(2023, 8, 9, 1, 2, 3)

    mapped = DERStatusMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERStatus)
    assert mapped.changed_time == changed_time

    actual = DERStatusMapper.map_to_response(scope, mapped, entity_site_id)
    assert isinstance(actual, DERStatus)

    assert_der_info_type_equal(DERStatus, expected, actual)
    assert actual.href.startswith("/my/prefix")
    assert f"/{entity_site_id}" in actual.href
    assert f"/{scope.display_site_id}" not in actual.href, "Should be using the entity site ID in the href"
    assert f"/{scope.site_id}" not in actual.href, "Should be using the entity site ID in the href"
    assert_datetime_equal(changed_time, actual.readingTime)


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_capability_roundtrip(optional_is_none: bool):
    """Tests that DERCapability mapping is reversible"""
    expected: DERCapability = generate_class_instance(
        DERCapability, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    expected.modesSupported = to_hex_binary(DERControlType.OP_MOD_CONNECT | DERControlType.OP_MOD_FREQ_DROOP)
    expected.doeModesSupported = to_hex_binary(DOESupportedMode.OP_MOD_EXPORT_LIMIT_W)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1991, href_prefix="/my/prefix"
    )
    entity_site_id = scope.site_id + 17
    changed_time = datetime(2023, 8, 9, 1, 2, 3)

    mapped = DERCapabilityMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERRating)
    assert mapped.changed_time == changed_time

    actual = DERCapabilityMapper.map_to_response(scope, mapped, entity_site_id)
    assert isinstance(actual, DERCapability)

    assert_der_info_type_equal(DERCapability, expected, actual)
    assert actual.href.startswith("/my/prefix")
    assert f"/{entity_site_id}" in actual.href
    assert f"/{scope.display_site_id}" not in actual.href, "Should be using the entity site ID in the href"
    assert f"/{scope.site_id}" not in actual.href, "Should be using the entity site ID in the href"


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_settings_roundtrip(optional_is_none: bool):
    """Tests that DERSettings mapping is reversible"""
    expected: DERSettings = generate_class_instance(
        DERSettings, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    expected.modesEnabled = to_hex_binary(DERControlType.OP_MOD_HFRT_MAY_TRIP | DERControlType.OP_MOD_FREQ_DROOP)
    expected.doeModesEnabled = to_hex_binary(DOESupportedMode.OP_MOD_EXPORT_LIMIT_W)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=9876, href_prefix="/my/prefix"
    )
    entity_site_id = scope.site_id + 17
    changed_time = datetime(2023, 8, 9, 1, 2, 4)

    mapped = DERSettingMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERSetting)
    assert mapped.changed_time == changed_time

    actual = DERSettingMapper.map_to_response(scope, mapped, entity_site_id)
    assert isinstance(actual, DERSettings)

    assert_der_info_type_equal(DERSettings, expected, actual)
    assert actual.href.startswith("/my/prefix")
    assert f"/{entity_site_id}" in actual.href
    assert f"/{scope.display_site_id}" not in actual.href, "Should be using the entity site ID in the href"
    assert f"/{scope.site_id}" not in actual.href, "Should be using the entity site ID in the href"
    assert_datetime_equal(changed_time, actual.updatedTime)
