from envoy_schema.server.schema.sep2 import identification

from envoy.server.mapper.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsMapper,
    FunctionSetAssignmentsResponse,
)
from envoy.server.request_state import RequestStateParameters
from tests.data.fake import generator


def test_map_to_response():
    """Simple sanity check on the mapper"""
    fsa_id = 4
    site_id = 9
    doe_count = 1  # End devices can only have 1 DOE associated with them
    tariff_count = 6
    rs_params = RequestStateParameters(1, None, None)
    result = FunctionSetAssignmentsMapper.map_to_response(
        rs_params=rs_params, fsa_id=fsa_id, site_id=site_id, doe_count=doe_count, tariff_count=tariff_count
    )
    assert result is not None
    assert isinstance(result, FunctionSetAssignmentsResponse)
    assert isinstance(result.TimeLink, identification.Link)
    assert isinstance(result.DERProgramListLink, identification.ListLink)
    assert isinstance(result.TariffProfileListLink, identification.ListLink)


def test_map_to_list_response():
    site_id = 10
    function_set_assignments = [generator.generate_class_instance(FunctionSetAssignmentsResponse)]
    rs_params = RequestStateParameters(1, None, None)

    result = FunctionSetAssignmentsMapper.map_to_list_response(
        rs_params=rs_params, function_set_assignments=function_set_assignments, site_id=site_id
    )
    assert result is not None
    assert isinstance(result, FunctionSetAssignmentsListResponse)
    assert len(result.FunctionSetAssignments) == 1
    assert isinstance(result.FunctionSetAssignments[0], FunctionSetAssignmentsResponse)
