import unittest.mock as mock
from datetime import datetime

import pytest
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.der import (
    AlarmStatusType,
    ConnectStatusType,
    DERAvailability,
    DERCapability,
    DERControlType,
    DERSettings,
    DERStatus,
)
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.sep2.der import (
    DERAvailabilityMapper,
    DERCapabilityMapper,
    DERSettingMapper,
    DERStatusMapper,
    to_hex_binary,
)
from envoy.server.mapper.sep2.end_device import EndDeviceListMapper, EndDeviceMapper
from envoy.server.model.site import Site, SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.request_state import RequestStateParameters
from tests.assert_time import assert_datetime_equal
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance, generate_value


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_avail_roundtrip(optional_is_none: bool):
    """Tests that DERAvailability mapping is reversible"""
    expected: DERAvailability = generate_class_instance(
        DERAvailability, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    site_id = 9876
    rs_params = RequestStateParameters(111, "/my/prefix")
    changed_time = datetime(2023, 8, 9, 1, 2, 3)

    mapped = DERAvailabilityMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERAvailability)
    assert mapped.changed_time == changed_time

    actual = DERAvailabilityMapper.map_to_response(rs_params, site_id, mapped)
    assert isinstance(actual, DERAvailability)

    assert_class_instance_equality(
        DERAvailability,
        expected,
        actual,
        ignored_properties=set(["href", "readingTime", "subscribable", "type"]),
    )
    assert actual.href.startswith("/my/prefix")
    assert str(site_id) in actual.href
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

    site_id = 9876
    rs_params = RequestStateParameters(111, "/my/prefix")
    changed_time = datetime(2023, 8, 9, 1, 2, 3)

    mapped = DERStatusMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERStatus)
    assert mapped.changed_time == changed_time

    actual = DERStatusMapper.map_to_response(rs_params, site_id, mapped)
    assert isinstance(actual, DERStatus)

    assert_class_instance_equality(
        DERStatus,
        expected,
        actual,
        ignored_properties=set(["href", "readingTime", "subscribable", "type"]),
    )
    assert actual.href.startswith("/my/prefix")
    assert str(site_id) in actual.href
    assert_datetime_equal(changed_time, actual.readingTime)


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_capability_roundtrip(optional_is_none: bool):
    """Tests that DERCapability mapping is reversible"""
    expected: DERCapability = generate_class_instance(
        DERCapability, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    expected.modesSupported = to_hex_binary(DERControlType.OP_MOD_CONNECT | DERControlType.OP_MOD_FREQ_DROOP)
    site_id = 9876
    rs_params = RequestStateParameters(111, "/my/prefix")
    changed_time = datetime(2023, 8, 9, 1, 2, 3)

    mapped = DERCapabilityMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERRating)
    assert mapped.changed_time == changed_time

    actual = DERCapabilityMapper.map_to_response(rs_params, site_id, mapped)
    assert isinstance(actual, DERCapability)

    assert_class_instance_equality(
        DERCapability,
        expected,
        actual,
        ignored_properties=set(["href", "subscribable", "type"]),
    )
    assert actual.href.startswith("/my/prefix")
    assert str(site_id) in actual.href


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_settings_roundtrip(optional_is_none: bool):
    """Tests that DERSettings mapping is reversible"""
    expected: DERSettings = generate_class_instance(
        DERSettings, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    expected.modesEnabled = to_hex_binary(DERControlType.OP_MOD_HFRT_MAY_TRIP | DERControlType.OP_MOD_FREQ_DROOP)
    site_id = 9876
    rs_params = RequestStateParameters(111, "/my/prefix")
    changed_time = datetime(2023, 8, 9, 1, 2, 4)

    mapped = DERSettingMapper.map_from_request(changed_time, expected)
    assert isinstance(mapped, SiteDERSetting)
    assert mapped.changed_time == changed_time

    actual = DERSettingMapper.map_to_response(rs_params, site_id, mapped)
    assert isinstance(actual, DERSettings)

    assert_class_instance_equality(
        DERSettings,
        expected,
        actual,
        ignored_properties=set(["href", "subscribable", "type", "updatedTime"]),
    )
    assert actual.href.startswith("/my/prefix")
    assert str(site_id) in actual.href
    assert_datetime_equal(changed_time, actual.updatedTime)
