from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.doe import (
    DoePageResponse,
    DynamicOperatingEnvelopeRequest,
    DynamicOperatingEnvelopeResponse,
)

from envoy.admin.mapper.doe import DoeListMapper
from envoy.server.model.doe import DynamicOperatingEnvelope


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_doe_mapper_from_request(optional_is_none: bool):
    req: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, optional_is_none=optional_is_none
    )

    changed_time = datetime(2021, 5, 6, 7, 8, 9)
    mdl = DoeListMapper.map_from_request(changed_time, [req])[0]

    assert isinstance(mdl, DynamicOperatingEnvelope)

    assert mdl.site_id == req.site_id
    assert mdl.calculation_log_id == req.calculation_log_id
    assert mdl.duration_seconds == req.duration_seconds
    assert mdl.import_limit_active_watts == req.import_limit_active_watts
    assert mdl.export_limit_watts == req.export_limit_watts
    assert mdl.start_time == req.start_time
    assert mdl.changed_time == changed_time
    assert mdl.created_time is None, "This should be left to the DB to populate"
    assert mdl.end_time == req.start_time + timedelta(seconds=req.duration_seconds)
    assert mdl.end_time.tzinfo == mdl.start_time.tzinfo

    assert not mdl.site
    assert not mdl.dynamic_operating_envelope_id


def test_doe_mapper_to_response():
    all: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False)
    optional: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=202, optional_is_none=True
    )

    all_mapped = DoeListMapper.map_to_response(all)
    assert isinstance(all_mapped, DynamicOperatingEnvelopeResponse)
    assert_class_instance_equality(DynamicOperatingEnvelopeResponse, all, all_mapped)  # These should just map 1-1

    optional_mapped = DoeListMapper.map_to_response(optional)
    assert isinstance(optional_mapped, DynamicOperatingEnvelopeResponse)
    assert_class_instance_equality(
        DynamicOperatingEnvelopeResponse,
        optional,
        optional_mapped,
        ignored_properties={"import_limit_active_watts", "export_limit_watts"},
    )  # These should just map 1-1
    assert optional_mapped.import_limit_active_watts == Decimal(0), "Workaround limitations on legacy API"
    assert optional_mapped.export_limit_watts == Decimal(0), "Workaround limitations on legacy API"


def test_doe_mapper_to_paged_response():
    does = [
        generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False),
        generate_class_instance(DynamicOperatingEnvelope, seed=202, optional_is_none=True),
        generate_class_instance(DynamicOperatingEnvelope, seed=303, optional_is_none=True, generate_relationships=True),
    ]

    limit = 123
    start = 456
    total_count = 789
    after = datetime(2022, 11, 12, 4, 5, 6)

    page_response = DoeListMapper.map_to_paged_response(total_count, limit, start, after, does)
    assert isinstance(page_response, DoePageResponse)
    assert_list_type(DynamicOperatingEnvelopeResponse, page_response.does, len(does))
    assert page_response.after == after
    assert page_response.limit == limit
    assert page_response.start == start
    assert page_response.total_count == total_count
