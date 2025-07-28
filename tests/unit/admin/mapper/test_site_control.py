from datetime import datetime, timedelta

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.site_control import (
    SiteControlGroupPageResponse,
    SiteControlGroupRequest,
    SiteControlGroupResponse,
    SiteControlPageResponse,
    SiteControlRequest,
    SiteControlResponse,
)

from envoy.admin.mapper.site_control import SiteControlGroupListMapper, SiteControlListMapper
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_site_control_group_mapper_roundtrip(optional_is_none: bool):
    original_req = generate_class_instance(SiteControlGroupRequest, optional_is_none=optional_is_none)
    changed_time = datetime(2022, 5, 6, 7, 8, 9)
    created_time = datetime(2023, 5, 6, 7, 8, 9)

    mdl = SiteControlGroupListMapper.map_from_request(original_req, changed_time)
    assert isinstance(mdl, SiteControlGroup)
    if mdl.site_control_group_id is None and mdl.created_time is None:
        # these should be set in the DB
        mdl.site_control_group_id = 1234
        mdl.created_time = created_time

    actual_req = SiteControlGroupListMapper.map_to_response(mdl)
    assert_class_instance_equality(SiteControlGroupRequest, original_req, actual_req)
    assert actual_req.changed_time == changed_time
    assert actual_req.created_time == created_time
    assert actual_req.site_control_group_id == 1234


def test_site_control_group_mapper_to_paged_response():
    groups = [
        generate_class_instance(SiteControlGroup, seed=101, optional_is_none=False),
        generate_class_instance(SiteControlGroup, seed=202, optional_is_none=True),
        generate_class_instance(SiteControlGroup, seed=303, optional_is_none=True, generate_relationships=True),
    ]

    limit = 123
    start = 456
    total_count = 789
    after = datetime(2022, 11, 12, 4, 5, 6)

    page_response = SiteControlGroupListMapper.map_to_paged_response(total_count, limit, start, after, groups)
    assert isinstance(page_response, SiteControlGroupPageResponse)
    assert_list_type(SiteControlGroupResponse, page_response.site_control_groups, len(groups))
    assert page_response.after == after
    assert page_response.limit == limit
    assert page_response.start == start
    assert page_response.total_count == total_count


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_site_control_mapper_roundtrip(optional_is_none: bool):
    original_req = generate_class_instance(SiteControlRequest, optional_is_none=optional_is_none)
    changed_time = datetime(2022, 5, 6, 7, 8, 9)
    site_control_group_id = 1325412

    mdl = SiteControlListMapper.map_from_request(site_control_group_id, changed_time, [original_req])[0]
    assert mdl.site_control_group_id == site_control_group_id
    assert mdl.changed_time == changed_time
    assert mdl.created_time is None, "Must be set in the DB"
    assert mdl.dynamic_operating_envelope_id is None, "Must be set in the DB"
    assert mdl.superseded is False, "Must default to False"
    mdl.created_time = datetime(2022, 1, 2, 3, 4, 5)
    mdl.dynamic_operating_envelope_id = 213123

    mdl.superseded = optional_is_none  # Ensure this field varies for different test cases
    actual_req = SiteControlListMapper.map_to_response(mdl)
    assert actual_req.superseded is optional_is_none

    assert_class_instance_equality(SiteControlRequest, original_req, actual_req, ignored_properties={"superseded"})


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_site_control_mapper_from_request(optional_is_none: bool):
    req = generate_class_instance(SiteControlRequest, optional_is_none=optional_is_none)
    site_control_group_id = 121

    changed_time = datetime(2021, 5, 6, 7, 8, 9)
    mdl = SiteControlListMapper.map_from_request(site_control_group_id, changed_time, [req])[0]

    assert isinstance(mdl, DynamicOperatingEnvelope)

    assert mdl.site_id == req.site_id
    assert mdl.calculation_log_id == req.calculation_log_id
    assert mdl.duration_seconds == req.duration_seconds
    assert mdl.import_limit_active_watts == req.import_limit_watts
    assert mdl.export_limit_watts == req.export_limit_watts
    assert mdl.start_time == req.start_time
    assert mdl.changed_time == changed_time
    assert mdl.created_time is None, "This should be left to the DB to populate"
    assert mdl.end_time == req.start_time + timedelta(seconds=req.duration_seconds)
    assert mdl.end_time.tzinfo == mdl.start_time.tzinfo

    assert not mdl.site
    assert not mdl.dynamic_operating_envelope_id


def test_site_control_mapper_to_paged_response():
    does = [
        generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False),
        generate_class_instance(DynamicOperatingEnvelope, seed=202, optional_is_none=True),
        generate_class_instance(DynamicOperatingEnvelope, seed=303, optional_is_none=True, generate_relationships=True),
    ]

    limit = 123
    start = 456
    total_count = 789
    after = datetime(2022, 11, 12, 4, 5, 6)

    page_response = SiteControlListMapper.map_to_paged_response(total_count, limit, start, after, does)
    assert isinstance(page_response, SiteControlPageResponse)
    assert_list_type(SiteControlResponse, page_response.controls, len(does))
    assert page_response.after == after
    assert page_response.limit == limit
    assert page_response.start == start
    assert page_response.total_count == total_count
