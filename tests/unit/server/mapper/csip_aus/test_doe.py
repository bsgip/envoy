from datetime import datetime, timedelta, timezone
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
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup
from envoy.server.model.site import DefaultSiteControl
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope


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
    assert result_all_set.DERControlBase_.opModImpLimW.multiplier == -4
    assert result_all_set.DERControlBase_.opModExpLimW.multiplier == -4
    assert result_all_set.DERControlBase_.opModImpLimW.value == int(doe.import_limit_active_watts * 10000)
    assert result_all_set.DERControlBase_.opModExpLimW.value == int(doe.export_limit_watts * 10000)
    assert result_all_set.DERControlBase_.opModGenLimW.multiplier == -4
    assert result_all_set.DERControlBase_.opModLoadLimW.multiplier == -4
    assert result_all_set.DERControlBase_.opModGenLimW.value == int(doe.generation_limit_active_watts * 10000)
    assert result_all_set.DERControlBase_.opModLoadLimW.value == int(doe.load_limit_active_watts * 10000)
    assert result_all_set.DERControlBase_.opModConnect == doe.set_connected
    assert result_all_set.DERControlBase_.opModEnergize == doe.set_energized
    assert result_all_set.randomizeStart == doe.randomize_start_seconds

    # Event status parsing is a little complex - this tries to check all the options
    if isinstance(doe, ArchiveDynamicOperatingEnvelope) and doe.deleted_time is not None:
        if randomize_seconds:
            assert result_all_set.EventStatus_.currentStatus == EventStatusType.CancelledWithRandomization
        else:
            assert result_all_set.EventStatus_.currentStatus == EventStatusType.Cancelled
        assert result_all_set.EventStatus_.dateTime == int(doe.deleted_time.timestamp())
    else:
        if is_active:
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
    assert result_optional.randomizeStart == randomize_seconds

    if isinstance(doe_opt, ArchiveDynamicOperatingEnvelope) and doe_opt.deleted_time is not None:
        if randomize_seconds:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.CancelledWithRandomization
        else:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.Cancelled
        assert result_optional.EventStatus_.dateTime == int(doe_opt.deleted_time.timestamp())
    else:
        if is_active:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.Active
        else:
            assert result_optional.EventStatus_.currentStatus == EventStatusType.Scheduled
        assert result_optional.EventStatus_.dateTime == int(doe_opt.changed_time.timestamp())


def test_map_default_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    doe_default: DefaultDoeConfiguration = generate_class_instance(
        DefaultDoeConfiguration, seed=101, optional_is_none=True
    )
    scope = generate_class_instance(BaseRequestScope)

    result_all_set = DERControlMapper.map_to_default_response(scope, doe_default, 1)
    assert result_all_set is not None
    assert isinstance(result_all_set, DefaultDERControl)
    assert isinstance(result_all_set.DERControlBase_, DERControlBase)
    assert isinstance(result_all_set.mRID, str)
    assert len(result_all_set.mRID) == 32, "Expected 128 bits encoded as hex"
    assert result_all_set.DERControlBase_.opModImpLimW is None
    assert result_all_set.DERControlBase_.opModExpLimW is None
    assert result_all_set.DERControlBase_.opModLoadLimW is None
    assert result_all_set.DERControlBase_.opModGenLimW is None
    assert result_all_set.setGradW is None


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
    default_doe = generate_class_instance(DefaultDoeConfiguration)

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
    assert result.DefaultDERControlLink is None
    assert f"/{site_control_group_id}" in result.href


@pytest.mark.parametrize(
    "control_groups_with_counts, total_control_groups, default_doe, fsa_id",
    [
        ([], 0, None, None),
        ([], 0, None, 123),
        ([], 0, generate_class_instance(DefaultSiteControl), None),
        (
            [
                (generate_class_instance(SiteControlGroup, seed=101), 99),
                (generate_class_instance(SiteControlGroup, seed=202, optional_is_none=True), 77),
            ],
            456,
            None,
            None,
        ),
        (
            [
                (generate_class_instance(SiteControlGroup, seed=101), 99),
                (generate_class_instance(SiteControlGroup, seed=202, optional_is_none=True), 77),
            ],
            456,
            generate_class_instance(DefaultSiteControl),
            None,
        ),
        (
            [
                (generate_class_instance(SiteControlGroup, seed=101), 11),
            ],
            789,
            generate_class_instance(DefaultSiteControl, optional_is_none=True),
            None,
        ),
        (
            [
                (generate_class_instance(SiteControlGroup, seed=101), 11),
            ],
            789,
            generate_class_instance(DefaultSiteControl, optional_is_none=True),
            123,
        ),
    ],
)
def test_map_derp_doe_program_list_response(
    control_groups_with_counts: list[tuple[SiteControlGroup, int]],
    total_control_groups: int,
    default_doe: Optional[DefaultSiteControl],
    fsa_id: Optional[int],
):
    """Shows that encoding a list of site_control_groups works with various counts"""
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope, href_prefix="/foo")
    poll_rate = 3
    result = DERProgramMapper.doe_program_list_response(
        scope, control_groups_with_counts, total_control_groups, default_doe, poll_rate, fsa_id
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
            if default_doe is not None:
                assert derp.DefaultDERControlLink is not None
                assert f"/{group.site_control_group_id}" in derp.DefaultDERControlLink.href
            else:
                assert derp.DefaultDERControlLink is None


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
