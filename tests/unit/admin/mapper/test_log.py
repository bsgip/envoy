from datetime import datetime

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.log import CalculationLogLabelValues as PublicLabelValues
from envoy_schema.admin.schema.log import CalculationLogRequest, CalculationLogResponse
from envoy_schema.admin.schema.log import CalculationLogVariableValues as PublicVariableValues

from envoy.admin.mapper.log import CalculationLogMapper
from envoy.server.model.log import (
    CalculationLog,
    CalculationLogLabelMetadata,
    CalculationLogLabelValue,
    CalculationLogVariableMetadata,
    CalculationLogVariableValue,
)


def test_map_to_response_handles_zero_to_none():
    log: CalculationLog = generate_class_instance(CalculationLog, seed=1001)
    log.variable_values = [
        generate_class_instance(CalculationLogVariableValue, seed=2002, site_id_snapshot=0),
        generate_class_instance(CalculationLogVariableValue, seed=3003, site_id_snapshot=10),
    ]

    log.label_values = [
        generate_class_instance(CalculationLogLabelValue, seed=4004, site_id_snapshot=0),
        generate_class_instance(CalculationLogLabelValue, seed=5005, site_id_snapshot=11),
    ]

    response: CalculationLogResponse = CalculationLogMapper.map_to_response(log)
    assert response.variable_values.site_ids == [None, 10]
    assert response.label_values.site_ids == [None, 11]


def test_map_from_request_handles_none_to_zero():
    request: CalculationLogRequest = generate_class_instance(CalculationLogRequest, seed=1001)
    request.variable_values = PublicVariableValues(
        variable_ids=[1, 2], site_ids=[None, 3], interval_periods=[4, 5], values=[6.6, 7.7]
    )
    request.label_values = PublicLabelValues(label_ids=[3, 4], site_ids=[None, 5], values=["aa", "bb"])

    log: CalculationLog = CalculationLogMapper.map_from_request(datetime.now(), request)
    assert_list_type(CalculationLogVariableValue, log.variable_values, count=len(request.variable_values.site_ids))
    assert [0, 3] == [e.site_id_snapshot for e in log.variable_values]
    assert [0, 5] == [e.site_id_snapshot for e in log.label_values]


def test_map_to_response_handles_empty_labels():
    log: CalculationLog = generate_class_instance(CalculationLog, seed=1001)
    log.variable_values = [
        generate_class_instance(CalculationLogVariableValue, seed=2002, site_id_snapshot=0),
        generate_class_instance(CalculationLogVariableValue, seed=3003, site_id_snapshot=10),
    ]

    log.label_values = []

    response: CalculationLogResponse = CalculationLogMapper.map_to_response(log)
    assert response.variable_values.site_ids == [None, 10]
    assert response.label_values is None, "If there are no values - they should map to None"


def test_map_to_response_handles_empty_variables():
    log: CalculationLog = generate_class_instance(CalculationLog, seed=1001)
    log.variable_values = []

    log.label_values = [
        generate_class_instance(CalculationLogLabelValue, seed=4004, site_id_snapshot=0),
        generate_class_instance(CalculationLogLabelValue, seed=5005, site_id_snapshot=11),
    ]

    response: CalculationLogResponse = CalculationLogMapper.map_to_response(log)
    assert response.variable_values is None, "If there are no values - they should map to None"
    assert response.label_values.site_ids == [None, 11]


@pytest.mark.parametrize("optional_as_none", [True, False])
def test_log_mapper_roundtrip(optional_as_none: bool):
    original: CalculationLog = generate_class_instance(
        CalculationLog, optional_is_none=optional_as_none, generate_relationships=True
    )

    changed_time = datetime(2021, 5, 6, 7, 8, 9)
    intermediate_model = CalculationLogMapper.map_to_response(original)
    assert isinstance(intermediate_model, CalculationLogResponse)

    actual = CalculationLogMapper.map_from_request(changed_time, intermediate_model)
    assert isinstance(actual, CalculationLog)

    # Assert top level object
    assert_class_instance_equality(
        CalculationLog, original, actual, ignored_properties=set(["created_time", "calculation_log_id"])
    )
    assert actual.created_time == changed_time

    # Assert Variable Metadata
    assert len(actual.variable_metadata) == len(original.variable_metadata)
    for actual_md, original_md in zip(actual.variable_metadata, original.variable_metadata):
        assert_class_instance_equality(
            CalculationLogVariableMetadata, original_md, actual_md, ignored_properties=set(["calculation_log_id"])
        )

    # Assert Variable Values
    assert len(actual.variable_values) == len(original.variable_values)
    for actual_val, original_val in zip(actual.variable_values, original.variable_values):
        assert_class_instance_equality(
            CalculationLogVariableValue,
            original_val,
            actual_val,
            ignored_properties=set(["calculation_log_id"]),
        )

    # Assert Label Metadata
    assert len(actual.label_metadata) == len(original.label_metadata)
    for actual_md, original_md in zip(actual.label_metadata, original.label_metadata):
        assert_class_instance_equality(
            CalculationLogLabelMetadata, original_md, actual_md, ignored_properties=set(["calculation_log_id"])
        )

    # Assert Label Values
    assert len(actual.label_values) == len(original.label_values)
    for actual_val, original_val in zip(actual.label_values, original.label_values):
        assert_class_instance_equality(
            CalculationLogLabelValue,
            original_val,
            actual_val,
            ignored_properties=set(["calculation_log_id"]),
        )
