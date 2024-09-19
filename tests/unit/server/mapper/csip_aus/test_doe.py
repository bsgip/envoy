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
from envoy_schema.server.schema.sep2.identification import Link, ListLink

from envoy.server.mapper.csip_aus.doe import DERControlListSource, DERControlMapper, DERProgramMapper
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.model.doe import DOE_DECIMAL_PLACES, DOE_DECIMAL_POWER, DynamicOperatingEnvelope
from envoy.server.request_scope import DeviceOrAggregatorRequestScope


def test_map_derc_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    doe: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False)
    doe_opt: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=202, optional_is_none=True
    )
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, href_prefix="/foo/bar"
    )

    result_all_set = DERControlMapper.map_to_response(scope, doe)
    assert result_all_set is not None
    assert isinstance(result_all_set, DERControlResponse)
    assert result_all_set.interval.start == doe.start_time.timestamp()
    assert result_all_set.interval.duration == doe.duration_seconds
    assert isinstance(result_all_set.DERControlBase_, DERControlBase)
    assert result_all_set.href.startswith(scope.href_prefix)
    assert f"/{scope.display_site_id}" in result_all_set.href
    assert result_all_set.DERControlBase_.opModImpLimW.multiplier == -DOE_DECIMAL_PLACES
    assert result_all_set.DERControlBase_.opModExpLimW.multiplier == -DOE_DECIMAL_PLACES
    assert result_all_set.DERControlBase_.opModImpLimW.value == int(doe.import_limit_active_watts * DOE_DECIMAL_POWER)
    assert result_all_set.DERControlBase_.opModExpLimW.value == int(doe.export_limit_watts * DOE_DECIMAL_POWER)

    result_optional = DERControlMapper.map_to_response(scope, doe_opt)
    assert result_optional is not None
    assert isinstance(result_optional, DERControlResponse)
    assert result_optional.interval.start == doe_opt.start_time.timestamp()
    assert result_optional.interval.duration == doe_opt.duration_seconds
    assert isinstance(result_optional.DERControlBase_, DERControlBase)
    assert result_optional.href.startswith(scope.href_prefix)
    assert f"/{scope.display_site_id}" in result_optional.href
    assert result_optional.DERControlBase_.opModImpLimW.multiplier == -DOE_DECIMAL_PLACES
    assert result_optional.DERControlBase_.opModExpLimW.multiplier == -DOE_DECIMAL_PLACES
    assert result_optional.DERControlBase_.opModImpLimW.value == int(
        doe_opt.import_limit_active_watts * DOE_DECIMAL_POWER
    )
    assert result_optional.DERControlBase_.opModExpLimW.value == int(doe_opt.export_limit_watts * DOE_DECIMAL_POWER)


def test_map_default_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    doe_default: DefaultDoeConfiguration = generate_class_instance(
        DefaultDoeConfiguration, seed=101, optional_is_none=True
    )

    result_all_set = DERControlMapper.map_to_default_response(doe_default)
    assert result_all_set is not None
    assert isinstance(result_all_set, DefaultDERControl)
    assert isinstance(result_all_set.DERControlBase_, DERControlBase)
    assert result_all_set.DERControlBase_.opModImpLimW.multiplier == -DOE_DECIMAL_PLACES
    assert result_all_set.DERControlBase_.opModExpLimW.multiplier == -DOE_DECIMAL_PLACES
    assert result_all_set.DERControlBase_.opModImpLimW.value == int(
        doe_default.import_limit_active_watts * DOE_DECIMAL_POWER
    )
    assert result_all_set.DERControlBase_.opModExpLimW.value == int(
        doe_default.export_limit_active_watts * DOE_DECIMAL_POWER
    )


def test_map_derc_to_list_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
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
    site_count = 199

    all_does = [doe1, doe2, doe3, doe4]
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=54121
    )

    result = DERControlMapper.map_to_list_response(scope, all_does, site_count, DERControlListSource.DER_CONTROL_LIST)
    assert result is not None
    assert isinstance(result, DERControlListResponse)
    assert result.all_ == site_count
    assert result.results == len(all_does)
    assert_list_type(DERControlResponse, result.DERControl, len(all_does))
    assert len(set([derc.mRID for derc in result.DERControl])) == len(
        all_does
    ), f"Expected {len(all_does)} unique mrid's in the children"
    assert str(scope.display_site_id) in result.href

    empty_result = DERControlMapper.map_to_list_response(
        scope, [], site_count, DERControlListSource.ACTIVE_DER_CONTROL_LIST
    )
    assert empty_result is not None
    assert isinstance(empty_result, DERControlListResponse)
    assert empty_result.all_ == site_count
    assert_list_type(DERControlResponse, empty_result.DERControl, 0)

    assert result.href != empty_result.href, "The derc list source is different so the hrefs should vary"


def test_map_derp_doe_program_response_with_default_doe():
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj (and there is
    a default doe specified)"""
    total_does = 456
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=54122
    )
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    result = DERProgramMapper.doe_program_response(scope, total_does, default_doe)
    assert result is not None
    assert isinstance(result, DERProgramResponse)
    assert result.href
    assert result.DERControlListLink is not None
    assert result.DERControlListLink.all_ == total_does
    assert result.DERControlListLink.href
    assert result.DERControlListLink.href != result.href

    assert result.ActiveDERControlListLink is not None
    assert isinstance(result.ActiveDERControlListLink, ListLink)
    assert result.ActiveDERControlListLink.href
    assert result.ActiveDERControlListLink.all_ == 1, "Should be 1 active listed as we have total does specified"

    assert result.DefaultDERControlLink is not None
    assert isinstance(result.DefaultDERControlLink, Link)
    assert result.DefaultDERControlLink.href

    assert result.DefaultDERControlLink.href != result.ActiveDERControlListLink.href

    assert str(scope.display_site_id) in result.href
    assert str(scope.display_site_id) in result.DERControlListLink.href
    assert str(scope.display_site_id) in result.DefaultDERControlLink.href
    assert str(scope.display_site_id) in result.ActiveDERControlListLink.href


def test_map_derp_doe_program_response_no_default_doe():
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj (and there is NO
    default doe specified)"""
    total_does = 456
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=54123
    )

    result = DERProgramMapper.doe_program_response(scope, total_does, None)
    assert result is not None
    assert isinstance(result, DERProgramResponse)

    assert result.ActiveDERControlListLink is not None
    assert isinstance(result.ActiveDERControlListLink, ListLink)
    assert result.ActiveDERControlListLink.href
    assert result.DefaultDERControlLink is None


def test_map_derp_doe_program_list_response_no_default_doe():
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj"""
    total_does = 456
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)

    result = DERProgramMapper.doe_program_list_response(scope, total_does, None)
    assert result is not None
    assert isinstance(result, DERProgramListResponse)
    assert result.href
    assert result.DERProgram is not None
    assert_list_type(DERProgramResponse, result.DERProgram, 1)
    assert result.all_ == 1
    assert result.results == 1

    # Default not specified
    assert result.DERProgram[0].DefaultDERControlLink is None
    assert result.DERProgram[0].ActiveDERControlListLink is not None


def test_map_derp_doe_program_list_response_with_default_doe():
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj"""
    total_does = 456
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    result = DERProgramMapper.doe_program_list_response(scope, total_does, default_doe)
    assert result is not None
    assert isinstance(result, DERProgramListResponse)
    assert result.href
    assert result.DERProgram is not None
    assert len(result.DERProgram) == 1
    assert all([isinstance(p, DERProgramResponse) for p in result.DERProgram])
    assert result.all_ == 1
    assert result.results == 1

    # Default has been specified
    assert result.DERProgram[0].DefaultDERControlLink is not None
    assert result.DERProgram[0].ActiveDERControlListLink is not None


def test_mrid_uniqueness():
    """Test our mrids for controls differ from programs even when the ID's are the same"""
    site_id = 1
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, site_id=site_id, display_site_id=site_id
    )
    doe: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope)
    doe.site_id = site_id
    doe.dynamic_operating_envelope_id = site_id  # intentionally the same as site_id

    program = DERProgramMapper.doe_program_response(scope, 999, None)
    control = DERControlMapper.map_to_response(scope, doe)
    assert program.mRID != control.mRID
