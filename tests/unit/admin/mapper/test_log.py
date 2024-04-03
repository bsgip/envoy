from datetime import datetime

import pytest
from envoy_schema.admin.schema.log import CalculationLogRequest, CalculationLogResponse

from envoy.admin.mapper.log import CalculationLogMapper
from envoy.server.model.log import CalculationLog, PowerFlowLog, PowerForecastLog, PowerTargetLog
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


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

    # Assert PowerFlow
    assert len(actual.power_flow_logs) == len(original.power_flow_logs)
    for actual_pf, original_pf in zip(actual.power_flow_logs, original.power_flow_logs):
        assert_class_instance_equality(
            PowerFlowLog, original_pf, actual_pf, ignored_properties=set(["power_flow_log_id"])
        )
