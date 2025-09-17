from typing import Optional

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2 import identification

from envoy.server.mapper.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsMapper,
    FunctionSetAssignmentsResponse,
)
from envoy.server.request_scope import SiteRequestScope


@pytest.mark.parametrize("tp_count, derp_count", [(0, 0), (None, 123), (456, None), (456, 444)])
def test_map_to_response(tp_count: Optional[int], derp_count: Optional[int]):
    """Simple sanity check on the mapper"""
    fsa_id = 214214
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=101, site_id=5616119, href_prefix="/foo")
    result = FunctionSetAssignmentsMapper.map_to_response(
        scope=scope, fsa_id=fsa_id, total_tp_links=tp_count, total_derp_links=derp_count
    )
    assert result is not None
    assert scope.href_prefix in result.href
    assert isinstance(result.mRID, str)
    assert len(result.mRID) == 32, "Expected 128 bits of hex characters"
    assert isinstance(result, FunctionSetAssignmentsResponse)
    assert isinstance(result.TimeLink, identification.Link)
    assert isinstance(result.DERProgramListLink, identification.ListLink)
    assert isinstance(result.TariffProfileListLink, identification.ListLink)

    assert result.TariffProfileListLink.all_ == tp_count
    assert result.DERProgramListLink.all_ == derp_count

    # Ensure href prefix is encoded
    assert result.TimeLink.href.startswith(scope.href_prefix)
    assert result.DERProgramListLink.href.startswith(scope.href_prefix)
    assert result.TariffProfileListLink.href.startswith(scope.href_prefix)

    # Ensure site id and FSA ID are being encoded
    assert f"/{fsa_id}" in result.DERProgramListLink.href
    assert f"/{scope.site_id}" in result.DERProgramListLink.href

    assert f"/{fsa_id}" in result.TariffProfileListLink.href
    assert f"/{scope.site_id}" in result.TariffProfileListLink.href


def test_map_to_list_response():
    fsa_ids = [1, 5]
    total_fsa_ids = 99123
    derp_counts_by_fsa_id = {1: 99, 2: 98}
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=101)

    result = FunctionSetAssignmentsMapper.map_to_list_response(
        scope=scope,
        fsa_ids=fsa_ids,
        total_fsa_ids=total_fsa_ids,
        pollrate_seconds=12,
        derp_counts_by_fsa_id=derp_counts_by_fsa_id,
    )

    assert result is not None
    assert scope.href_prefix in result.href
    assert isinstance(result, FunctionSetAssignmentsListResponse)

    assert_list_type(FunctionSetAssignmentsResponse, result.FunctionSetAssignments, len(fsa_ids))
    assert result.pollRate == 12
    assert result.all_ == total_fsa_ids
    assert result.results == len(fsa_ids)
    assert result.FunctionSetAssignments[0].DERProgramListLink.all_ == 99
    assert result.FunctionSetAssignments[1].DERProgramListLink.all_ is None
