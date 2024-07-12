from datetime import datetime
from typing import Optional

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal
from assertical.fake.generator import generate_class_instance
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
from envoy.server.request_state import RequestStateParameters


def test_der_mapping():
    all_set: SiteDER = generate_class_instance(SiteDER, seed=101, optional_is_none=False, generate_relationships=True)
    with_none: SiteDER = generate_class_instance(SiteDER, seed=202, optional_is_none=True, generate_relationships=True)

    rs_params = RequestStateParameters(111, None, "/my/prefix")
    derp_id = "my_derp_id"

    mapped_all_set = DERMapper.map_to_response(rs_params, all_set, derp_id)
    assert isinstance(mapped_all_set, DER)

    assert mapped_all_set.href.startswith("/my/prefix")
    assert str(all_set.site_id) in mapped_all_set.href
    assert isinstance(mapped_all_set.AssociatedDERProgramListLink, Link)
    assert isinstance(mapped_all_set.CurrentDERProgramLink, Link)
    assert isinstance(mapped_all_set.DERAvailabilityLink, Link)
    assert isinstance(mapped_all_set.DERCapabilityLink, Link)
    assert isinstance(mapped_all_set.DERSettingsLink, Link)
    assert isinstance(mapped_all_set.DERStatusLink, Link)
    assert derp_id in mapped_all_set.CurrentDERProgramLink.href
    assert str(all_set.site_id) in mapped_all_set.CurrentDERProgramLink.href

    # Test with NO active der program id
    mapped_all_set_no_actderp = DERMapper.map_to_response(rs_params, all_set, None)
    assert isinstance(mapped_all_set_no_actderp, DER)
    assert mapped_all_set_no_actderp.href.startswith("/my/prefix")
    assert str(all_set.site_id) in mapped_all_set_no_actderp.href
    assert mapped_all_set_no_actderp.CurrentDERProgramLink is None

    mapped_with_none = DERMapper.map_to_response(rs_params, with_none, derp_id)
    assert isinstance(mapped_with_none, DER)
    assert mapped_with_none.href.startswith("/my/prefix")
    assert str(with_none.site_id) in mapped_with_none.href
    assert isinstance(mapped_with_none.AssociatedDERProgramListLink, Link)
    assert isinstance(mapped_with_none.CurrentDERProgramLink, Link)
    assert isinstance(mapped_with_none.DERAvailabilityLink, Link)
    assert isinstance(mapped_with_none.DERCapabilityLink, Link)
    assert isinstance(mapped_with_none.DERSettingsLink, Link)
    assert isinstance(mapped_with_none.DERStatusLink, Link)
    assert derp_id in mapped_with_none.CurrentDERProgramLink.href
    assert str(with_none.site_id) in mapped_with_none.CurrentDERProgramLink.href


def test_der_list():
    ders: list[tuple[SiteDER, Optional[str]]] = [
        (generate_class_instance(SiteDER, seed=101, optional_is_none=False, generate_relationships=True), "DERPID1"),
        (generate_class_instance(SiteDER, seed=202, optional_is_none=False, generate_relationships=True), None),
        (generate_class_instance(SiteDER, seed=303, optional_is_none=True, generate_relationships=True), None),
        (generate_class_instance(SiteDER, seed=404, optional_is_none=True, generate_relationships=True), "DERPID2"),
    ]

    rs_params = RequestStateParameters(111, None, "/my/prefix")
    site_id = 11
    poll_rate = 99
    count = 42

    mapped = DERMapper.map_to_list_response(rs_params, site_id, poll_rate, ders, count)
    assert isinstance(mapped, DERListResponse)
    assert mapped.results == 4
    assert mapped.all_ == count
    assert mapped.pollRate == poll_rate
    assert len(mapped.DER_) == 4
    assert all([isinstance(x, DER) for x in mapped.DER_])


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_der_avail_roundtrip(optional_is_none: bool):
    """Tests that DERAvailability mapping is reversible"""
    expected: DERAvailability = generate_class_instance(
        DERAvailability, seed=101, optional_is_none=optional_is_none, generate_relationships=True
    )
    site_id = 9876
    rs_params = RequestStateParameters(111, None, "/my/prefix")
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
    rs_params = RequestStateParameters(111, None, "/my/prefix")
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
    rs_params = RequestStateParameters(111, None, "/my/prefix")
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
    rs_params = RequestStateParameters(111, None, "/my/prefix")
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
