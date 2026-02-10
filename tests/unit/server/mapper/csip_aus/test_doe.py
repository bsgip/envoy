from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import product
from typing import Optional, Union

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.der import (
    DefaultDERControl,
    DERControlBase,
    DERControlListResponse,
    DERControlResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from envoy_schema.server.schema.sep2.event import EventStatusType
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.uri import DERProgramFSAListUri, DERProgramListUri

from envoy.server.mapper.csip_aus.doe import DERControlListSource, DERControlMapper, DERProgramMapper
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope, ArchiveSiteControlGroup
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup, SiteControlGroupDefault
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope


@pytest.mark.parametrize(
    "percent, expected",
    [
        (Decimal("1.23"), 123),
        (Decimal("-4.56"), -456),
        (Decimal("0.000"), 0),
        (Decimal("100.00"), 10000),
        (Decimal("-100.00"), -10000),
    ],
)
def test_map_to_hundredths(percent: Decimal, expected: int):
    actual = DERControlMapper.map_to_hundredths(percent)
    assert isinstance(actual, int)
    assert actual == expected


@pytest.mark.parametrize(
    "watts, requested_multiplier, expected_value, expected_multiplier",
    [
        # Small values that fit in Int16 with the requested multiplier
        (Decimal("100"), 0, 100, 0),
        (Decimal("100"), -2, 10000, -2),
        (Decimal("1.5"), -2, 150, -2),
        # Large values that require multiplier adjustment to fit Int16
        # Algorithm: ceil(log10(|p| / 32767)) gives minimum multiplier needed
        (Decimal("60000"), 0, 6000, 1),
        (Decimal("100000"), 0, 10000, 1),
        (Decimal("500000"), 0, 5000, 2),
        # Values with negative multipliers that would overflow
        (Decimal("5"), -4, 5000, -3),
        (Decimal("10"), -4, 10000, -3),
        # Negative power values
        (Decimal("-60000"), 0, -6000, 1),
        (Decimal("-100"), -2, -10000, -2),
        # Zero
        (Decimal("0"), 0, 0, 0),
        (Decimal("0"), -4, 0, -4),
        # Values exactly at boundaries
        (Decimal("32767"), 0, 32767, 0),  # Int16 max
        (Decimal("-32768"), 0, -32768, 0),  # Int16 min
        (Decimal("32768"), 0, 3276, 1),  # One over
        # Very large values
        (Decimal("1000000"), 0, 10000, 2),
        (Decimal("10000000"), 0, 10000, 3),
    ],
)
def test_map_to_active_power(watts: Decimal, requested_multiplier: int, expected_value: int, expected_multiplier: int):
    """Tests that map_to_active_power correctly encodes power values with appropriate multipliers.

    IEEE 2030.5 uses Int16 for ActivePower.value (-32768 to 32767), so the mapper must
    automatically adjust the multiplier when the value would exceed this range.
    """
    result = DERControlMapper.map_to_active_power(watts, requested_multiplier)

    assert -32768 <= result.value <= 32767
    assert result.value == expected_value, f"Expected value={expected_value}, got {result.value}"
    assert result.multiplier == expected_multiplier, f"Expected {expected_multiplier}, got {result.multiplier}"

    # Verify the actual watts is approximately correct just in case
    actual_watts = Decimal(result.value) * (Decimal(10) ** result.multiplier)
    tolerance = Decimal(10) ** result.multiplier  # Tolerance is one unit
    assert abs(actual_watts - watts) < tolerance, f"Expected ~{watts}W, got {actual_watts}W (tolerance: {tolerance})"


@pytest.mark.parametrize(
    "doe_type, randomize_seconds, is_active",
    product([DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope], [-123, 123, None], [True, False]),
)
def test_map_derc_to_response(
    doe_type: type[Union[DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope]],
    randomize_seconds: Optional[int],
    is_active: bool,
):
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""

    doe_start_time = datetime(2023, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    doe_duration = 300
    doe_end_time = doe_start_time + timedelta(seconds=doe_duration)

    if is_active:
        now = doe_start_time + timedelta(seconds=1)
    else:
        now = doe_start_time - timedelta(seconds=1)

    site_control_group_id = 88776654
    doe = generate_class_instance(
        doe_type,
        seed=101,
        optional_is_none=False,
        randomize_start_seconds=randomize_seconds,
        start_time=doe_start_time,
        end_time=doe_end_time,
        duration_seconds=doe_duration,
    )
    doe_opt = generate_class_instance(
        doe_type,
        seed=202,
        optional_is_none=True,
        randomize_start_seconds=randomize_seconds,
        start_time=doe_start_time,
        end_time=doe_end_time,
        duration_seconds=doe_duration,
    )
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, href_prefix="/foo/bar"
    )

    result_all_set = DERControlMapper.map_to_response(scope, site_control_group_id, doe, -4, now)
    assert result_all_set is not None
    assert isinstance(result_all_set, DERControlResponse)
    assert result_all_set.interval.start == doe.start_time.timestamp()
    assert result_all_set.interval.duration == doe.duration_seconds
    assert isinstance(result_all_set.DERControlBase_, DERControlBase)
    assert result_all_set.href.startswith(scope.href_prefix)
    assert f"/{scope.display_site_id}" in result_all_set.href
    assert f"/{site_control_group_id}" in result_all_set.href

    # The multiplier should be at least -4, but may be adjusted to fit Int16 range (IEEE 2030.5 uses Int16 for value)
    def check_active_power(ap, expected_watts):
        INT16_MAX = 32767
        INT16_MIN = -32768
        assert INT16_MIN <= ap.value <= INT16_MAX
        actual_watts = Decimal(ap.value) * (Decimal(10) ** ap.multiplier)
        assert actual_watts == expected_watts
        assert ap.multiplier >= -4

    check_active_power(result_all_set.DERControlBase_.opModImpLimW, doe.import_limit_active_watts)
    check_active_power(result_all_set.DERControlBase_.opModExpLimW, doe.export_limit_watts)
    check_active_power(result_all_set.DERControlBase_.opModGenLimW, doe.generation_limit_active_watts)
    check_active_power(result_all_set.DERControlBase_.opModLoadLimW, doe.load_limit_active_watts)
    assert result_all_set.DERControlBase_.opModConnect == doe.set_connected
    assert result_all_set.DERControlBase_.opModEnergize == doe.set_energized
    assert result_all_set.DERControlBase_.opModFixedW == DERControlMapper.map_to_hundredths(doe.set_point_percentage)
    assert result_all_set.randomizeStart == doe.randomize_start_seconds
    assert result_all_set.DERControlBase_.rampTms == DERControlMapper.map_to_hundredths(doe.ramp_time_seconds)

    # Event status parsing is a little complex - this tries to check all the options
    if isinstance(doe, ArchiveDynamicOperatingEnvelope) and doe.deleted_time is not None:
        if randomize_seconds:
            assert result_all_set.EventStatus_.currentStatus == EventStatusType.CancelledWithRandomization
        else:
            assert result_all_set.EventStatus_.currentStatus == EventStatusType.Cancelled
        assert result_all_set.EventStatus_.dateTime == int(doe.deleted_time.timestamp())
    else:
        if doe.superseded:
            assert result_all_set.EventStatus_.currentStatus == EventStatusType.Superseded
        elif is_active:
            assert result_all_set.EventStatus_.currentStatus == EventStatusType.Active
        else:
            assert result_all_set.EventStatus_.currentStatus == EventStatusType.Scheduled
        assert result_all_set.EventStatus_.dateTime == int(doe.changed_time.timestamp())

    result_optional = DERControlMapper.map_to_response(scope, site_control_group_id, doe_opt, -3, now)
    assert result_optional is not None
    assert isinstance(result_optional, DERControlResponse)
    assert result_optional.interval.start == doe_opt.start_time.timestamp()
    assert result_optional.interval.duration == doe_opt.duration_seconds
    assert isinstance(result_optional.DERControlBase_, DERControlBase)
    assert result_optional.href.startswith(scope.href_prefix)
    assert f"/{scope.display_site_id}" in result_optional.href
    assert f"/{site_control_group_id}" in result_optional.href
    assert result_optional.DERControlBase_.opModImpLimW is None
    assert result_optional.DERControlBase_.opModExpLimW is None
    assert result_optional.DERControlBase_.opModGenLimW is None
    assert result_optional.DERControlBase_.opModLoadLimW is None
    assert result_optional.DERControlBase_.opModConnect is None
    assert result_optional.DERControlBase_.opModEnergize is None
    assert result_optional.DERControlBase_.opModFixedW is None
    assert result_optional.randomizeStart == randomize_seconds
    assert result_optional.DERControlBase_.rampTms is None

    if isinstance(doe_opt, ArchiveDynamicOperatingEnvelope) and doe_opt.deleted_time is not None:
        if randomize_seconds:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.CancelledWithRandomization
        else:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.Cancelled
        assert result_optional.EventStatus_.dateTime == int(doe_opt.deleted_time.timestamp())
    else:
        if doe_opt.superseded:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.Superseded
        elif is_active:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.Active
        else:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.Scheduled
        assert result_optional.EventStatus_.dateTime == int(doe_opt.changed_time.timestamp())


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_map_default_to_response(optional_is_none: bool):
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    doe_default = generate_class_instance(SiteControlGroupDefault, seed=101, optional_is_none=optional_is_none)
    scope = generate_class_instance(BaseRequestScope, href_prefix="/my/prefix/")
    pow_10 = 1
    derp_id = 2
    site_id = 3

    result = DERControlMapper.map_to_default_response(scope, doe_default, site_id, derp_id, pow_10)
    assert result is not None
    assert isinstance(result, DefaultDERControl)
    assert isinstance(result.DERControlBase_, DERControlBase)
    assert isinstance(result.mRID, str)
    assert len(result.mRID) == 32, "Expected 128 bits encoded as hex"
    assert result.href.startswith("/my/prefix/")
    assert f"/{site_id}/" in result.href
    assert f"/{derp_id}/" in result.href
    assert result.version == doe_default.version

    if doe_default.export_limit_active_watts is None:
        assert result.DERControlBase_.opModExpLimW is None
    else:
        assert result.DERControlBase_.opModExpLimW == DERControlMapper.map_to_active_power(
            doe_default.export_limit_active_watts, pow_10
        )

    if doe_default.import_limit_active_watts is None:
        assert result.DERControlBase_.opModImpLimW is None
    else:
        assert result.DERControlBase_.opModImpLimW == DERControlMapper.map_to_active_power(
            doe_default.import_limit_active_watts, pow_10
        )

    if doe_default.load_limit_active_watts is None:
        assert result.DERControlBase_.opModLoadLimW is None
    else:
        assert result.DERControlBase_.opModLoadLimW == DERControlMapper.map_to_active_power(
            doe_default.load_limit_active_watts, pow_10
        )

    if doe_default.generation_limit_active_watts is None:
        assert result.DERControlBase_.opModGenLimW is None
    else:
        assert result.DERControlBase_.opModGenLimW == DERControlMapper.map_to_active_power(
            doe_default.generation_limit_active_watts, pow_10
        )

    assert result.setGradW == doe_default.ramp_rate_percent_per_second


def test_map_derc_to_list_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    site_control_group_id = 88776654
    now = datetime(1990, 1, 2, tzinfo=timezone.utc)

    doe1: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=303, optional_is_none=False, generate_relationships=False
    )
    doe2: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=404, optional_is_none=False, generate_relationships=True
    )
    doe3: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=505, optional_is_none=True, generate_relationships=False
    )
    doe4: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=606, optional_is_none=True, generate_relationships=True
    )
    doe_count = 199

    all_does = [doe1, doe2, doe3, doe4]
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=54121
    )

    result = DERControlMapper.map_to_list_response(
        scope, site_control_group_id, all_does, doe_count, DERControlListSource.DER_CONTROL_LIST, 1, now
    )
    assert result is not None
    assert isinstance(result, DERControlListResponse)
    assert result.all_ == doe_count
    assert result.results == len(all_does)
    assert_list_type(DERControlResponse, result.DERControl, len(all_does))
    assert len(set([derc.mRID for derc in result.DERControl])) == len(
        all_does
    ), f"Expected {len(all_does)} unique mrid's in the children"
    assert str(scope.display_site_id) in result.href
    assert f"/{site_control_group_id}" in result.href
    assert result.DERControl[0].DERControlBase_.opModGenLimW.multiplier == 1

    empty_result = DERControlMapper.map_to_list_response(
        scope, site_control_group_id, [], doe_count, DERControlListSource.ACTIVE_DER_CONTROL_LIST, 1, now
    )
    assert empty_result is not None
    assert isinstance(empty_result, DERControlListResponse)
    assert empty_result.all_ == doe_count
    assert_list_type(DERControlResponse, empty_result.DERControl, 0)

    assert result.href != empty_result.href, "The derc list source is different so the hrefs should vary"


@pytest.mark.parametrize("total_does", [None, 0, 456])
def test_map_derp_doe_program_response_with_default_doe(total_does: Optional[int]):
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj (and there is
    a default doe specified)"""
    site_control_group_id = 88776654
    site_control_group = generate_class_instance(SiteControlGroup, site_control_group_id=site_control_group_id)

    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=54122
    )
    default_doe = generate_class_instance(SiteControlGroupDefault)

    result = DERProgramMapper.doe_program_response(scope, total_does, site_control_group, default_doe)
    assert result is not None
    assert isinstance(result, DERProgramResponse)
    assert result.href
    assert result.DERControlListLink is not None
    assert result.DERControlListLink.all_ == total_does
    assert result.DERControlListLink.href
    assert result.DERControlListLink.href != result.href
    assert isinstance(result.mRID, str)
    assert len(result.mRID) == 32, "Expected 128 bits of hex"

    assert result.ActiveDERControlListLink is not None
    assert isinstance(result.ActiveDERControlListLink, ListLink)
    assert result.ActiveDERControlListLink.href

    if total_does is None:
        assert result.ActiveDERControlListLink.all_ is None
    elif total_does == 0:
        assert result.ActiveDERControlListLink.all_ == 0, "Should be 0 active listed as we have no DOEs"
    else:
        assert result.ActiveDERControlListLink.all_ == 1, "Should be 1 active listed as we have total does specified"

    assert result.DefaultDERControlLink is not None
    assert isinstance(result.DefaultDERControlLink, Link)
    assert result.DefaultDERControlLink.href

    assert result.DefaultDERControlLink.href != result.ActiveDERControlListLink.href

    assert str(scope.display_site_id) in result.href
    assert f"/{site_control_group_id}" in result.href
    assert str(scope.display_site_id) in result.DERControlListLink.href
    assert f"/{site_control_group_id}" in result.DERControlListLink.href
    assert str(scope.display_site_id) in result.DefaultDERControlLink.href
    assert f"/{site_control_group_id}" in result.DefaultDERControlLink.href
    assert str(scope.display_site_id) in result.ActiveDERControlListLink.href
    assert f"/{site_control_group_id}" in result.ActiveDERControlListLink.href


@pytest.mark.parametrize("scg_type", [SiteControlGroup, ArchiveSiteControlGroup])
def test_map_derp_doe_program_response_no_default_doe(scg_type: type[Union[SiteControlGroup, ArchiveSiteControlGroup]]):
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj (and there is NO
    default doe specified)"""

    site_control_group_id = 88776654
    site_control_group = generate_class_instance(scg_type, site_control_group_id=site_control_group_id)
    total_does = 456
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=54123
    )

    result = DERProgramMapper.doe_program_response(scope, total_does, site_control_group, None)
    assert result is not None
    assert isinstance(result, DERProgramResponse)

    assert result.ActiveDERControlListLink is not None
    assert isinstance(result.ActiveDERControlListLink, ListLink)
    assert result.ActiveDERControlListLink.href
    assert result.DefaultDERControlLink is not None
    assert isinstance(result.DefaultDERControlLink, Link)
    assert result.DefaultDERControlLink.href
    assert f"/{site_control_group_id}" in result.DefaultDERControlLink.href
    assert f"/{site_control_group_id}" in result.href


@pytest.mark.parametrize(
    "control_groups_with_counts, total_control_groups, fsa_id",
    [
        ([], 0, None),
        ([], 0, 123),
        ([], 0, None),
        (
            [
                (
                    generate_class_instance(
                        SiteControlGroup,
                        seed=101,
                        site_control_group_default=generate_class_instance(SiteControlGroupDefault),
                    ),
                    99,
                ),
                (generate_class_instance(SiteControlGroup, seed=202, optional_is_none=True), 77),
            ],
            456,
            None,
        ),
        (
            [
                (generate_class_instance(SiteControlGroup, seed=101), 99),
                (
                    generate_class_instance(
                        SiteControlGroup,
                        seed=202,
                        optional_is_none=True,
                        site_control_group_default=generate_class_instance(SiteControlGroupDefault),
                    ),
                    77,
                ),
            ],
            456,
            None,
        ),
        (
            [
                (
                    generate_class_instance(
                        SiteControlGroup,
                        seed=101,
                        site_control_group_default=generate_class_instance(SiteControlGroupDefault),
                    ),
                    11,
                ),
            ],
            789,
            None,
        ),
        (
            [
                (generate_class_instance(SiteControlGroup, seed=101), 11),
            ],
            789,
            123,
        ),
    ],
)
def test_map_derp_doe_program_list_response(
    control_groups_with_counts: list[tuple[SiteControlGroup, int]],
    total_control_groups: int,
    fsa_id: Optional[int],
):
    """Shows that encoding a list of site_control_groups works with various counts"""
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope, href_prefix="/foo")
    poll_rate = 3
    result = DERProgramMapper.doe_program_list_response(
        scope, control_groups_with_counts, total_control_groups, poll_rate, fsa_id
    )
    assert result is not None
    assert isinstance(result, DERProgramListResponse)
    assert result.pollRate == poll_rate

    assert result.href.startswith(scope.href_prefix)
    if fsa_id is None:
        assert result.href.endswith(DERProgramListUri.format(site_id=scope.display_site_id))
    else:
        assert result.href.endswith(DERProgramFSAListUri.format(site_id=scope.display_site_id, fsa_id=fsa_id))

    assert result.all_ == total_control_groups
    if len(control_groups_with_counts) == 0:
        assert result.DERProgram is None or len(result.DERProgram) == 0
        assert result.results == 0
    else:
        assert result.DERProgram is not None
        assert result.results == len(control_groups_with_counts)
        assert_list_type(DERProgramResponse, result.DERProgram, len(control_groups_with_counts))
        for derp, (group, group_count) in zip(result.DERProgram, control_groups_with_counts):
            derp.DERControlListLink.all_ == group_count
            assert derp.DefaultDERControlLink is not None
            assert f"/{group.site_control_group_id}" in derp.DefaultDERControlLink.href


def test_mrid_uniqueness():
    """Test our mrids for controls differ from programs even when the ID's are the same"""

    site_control_group = generate_class_instance(SiteControlGroup, seed=101)
    site_id = 1
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, site_id=site_id, display_site_id=site_id
    )
    doe: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope)
    doe.site_id = site_id
    doe.dynamic_operating_envelope_id = site_id  # intentionally the same as site_id
    now = datetime(2022, 11, 3, tzinfo=timezone.utc)

    program = DERProgramMapper.doe_program_response(scope, 999, site_control_group, None)
    control = DERControlMapper.map_to_response(scope, site_control_group.site_control_group_id, doe, 1, now)
    assert program.mRID != control.mRID
