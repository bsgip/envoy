from envoy.server.mapper.csip_aus.doe import DERControlMapper, DERProgramMapper
from envoy.server.model.doe import DOE_DECIMAL_PLACES, DOE_DECIMAL_POWER, DynamicOperatingEnvelope
from envoy.server.schema.sep2.der import (
    DERControlBase,
    DERControlListResponse,
    DERControlResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from tests.data.fake.generator import generate_class_instance


def test_map_derc_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    doe: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False)
    doe_opt: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=202, optional_is_none=True
    )

    result_all_set = DERControlMapper.map_to_response(doe)
    assert result_all_set is not None
    assert isinstance(result_all_set, DERControlResponse)
    assert result_all_set.interval.start == doe.start_time.timestamp()
    assert result_all_set.interval.duration == doe.duration_seconds
    assert isinstance(result_all_set.DERControlBase_, DERControlBase)
    assert result_all_set.DERControlBase_.opModImpLimW.multiplier == DOE_DECIMAL_PLACES
    assert result_all_set.DERControlBase_.opModExpLimW.multiplier == DOE_DECIMAL_PLACES
    assert result_all_set.DERControlBase_.opModImpLimW.value == int(doe.import_limit_active_watts * DOE_DECIMAL_POWER)
    assert result_all_set.DERControlBase_.opModExpLimW.value == int(doe.export_limit_watts * DOE_DECIMAL_POWER)

    result_optional = DERControlMapper.map_to_response(doe_opt)
    assert result_optional is not None
    assert isinstance(result_optional, DERControlResponse)
    assert result_optional.interval.start == doe_opt.start_time.timestamp()
    assert result_optional.interval.duration == doe_opt.duration_seconds
    assert isinstance(result_optional.DERControlBase_, DERControlBase)
    assert result_optional.DERControlBase_.opModImpLimW.multiplier == DOE_DECIMAL_PLACES
    assert result_optional.DERControlBase_.opModExpLimW.multiplier == DOE_DECIMAL_PLACES
    assert result_optional.DERControlBase_.opModImpLimW.value == int(
        doe_opt.import_limit_active_watts * DOE_DECIMAL_POWER
    )
    assert result_optional.DERControlBase_.opModExpLimW.value == int(doe_opt.export_limit_watts * DOE_DECIMAL_POWER)


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
    site_id = 54121

    result = DERControlMapper.map_to_list_response(all_does, site_count, site_id)
    assert result is not None
    assert isinstance(result, DERControlListResponse)
    assert result.all_ == site_count
    assert result.results == len(all_does)
    assert isinstance(result.DERControl, list)
    assert len(result.DERControl) == len(all_does)
    assert all([isinstance(derc, DERControlResponse) for derc in result.DERControl])
    assert len(set([derc.mRID for derc in result.DERControl])) == len(
        all_does
    ), f"Expected {len(all_does)} unique mrid's in the children"
    assert str(site_id) in result.href

    empty_result = DERControlMapper.map_to_list_response([], site_count, site_id)
    assert empty_result is not None
    assert isinstance(empty_result, DERControlListResponse)
    assert empty_result.all_ == site_count
    assert isinstance(empty_result.DERControl, list)
    assert len(empty_result.DERControl) == 0


def test_map_derp_doe_program_response():
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj"""
    site_id = 123
    total_does = 456

    result = DERProgramMapper.doe_program_response(site_id, total_does)
    assert result is not None
    assert isinstance(result, DERProgramResponse)
    assert result.href
    assert result.DERControlListLink is not None
    assert result.DERControlListLink.all_ == total_does
    assert result.DERControlListLink.href
    assert result.DERControlListLink.href != result.href


def test_map_derp_doe_program_list_response():
    """Simple sanity check on the mapper to ensure nothing is raised when creating this static obj"""
    site_id = 123
    total_does = 456

    result = DERProgramMapper.doe_program_list_response(site_id, total_does)
    assert result is not None
    assert isinstance(result, DERProgramListResponse)
    assert result.href
    assert result.DERProgram is not None
    assert len(result.DERProgram) == 1
    assert all([isinstance(p, DERProgramResponse) for p in result.DERProgram])
    assert result.all_ == 1
    assert result.results == 1


def test_mrid_uniqueness():
    """Test our mrids for controls differ from programs even when the ID's are the same"""
    site_id = 1
    doe: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope)
    doe.site_id = site_id
    doe.dynamic_operating_envelope_id = site_id  # intentionally the same as site_id

    program = DERProgramMapper.doe_program_response(site_id, 999)
    control = DERControlMapper.map_to_response(doe)
    assert program.mRID != control.mRID
