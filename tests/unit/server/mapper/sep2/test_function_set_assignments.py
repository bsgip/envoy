from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2 import identification

from envoy.server.mapper.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsMapper,
    FunctionSetAssignmentsResponse,
)
from envoy.server.request_scope import SiteRequestScope


def test_map_to_response():
    """Simple sanity check on the mapper"""
    fsa_id = 4
    doe_count = 1  # End devices can only have 1 DOE associated with them
    tariff_count = 6
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=101)
    result = FunctionSetAssignmentsMapper.map_to_response(
        scope=scope, fsa_id=fsa_id, doe_count=doe_count, tariff_count=tariff_count
    )
    assert result is not None
    assert scope.href_prefix in result.href
    assert isinstance(result.mRID, str)
    assert len(result.mRID) == 32, "Expected 128 bits of hex characters"
    assert isinstance(result, FunctionSetAssignmentsResponse)
    assert isinstance(result.TimeLink, identification.Link)
    assert isinstance(result.DERProgramListLink, identification.ListLink)
    assert isinstance(result.TariffProfileListLink, identification.ListLink)


def test_map_to_list_response():
    function_set_assignments = [generate_class_instance(FunctionSetAssignmentsResponse)]
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=101)

    result = FunctionSetAssignmentsMapper.map_to_list_response(
        scope=scope, function_set_assignments=function_set_assignments
    )

    assert result is not None
    assert scope.href_prefix in result.href
    assert isinstance(result, FunctionSetAssignmentsListResponse)
    assert len(result.FunctionSetAssignments) == 1
    assert isinstance(result.FunctionSetAssignments[0], FunctionSetAssignmentsResponse)
