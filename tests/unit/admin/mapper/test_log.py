from datetime import datetime

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.log import CalculationLogResponse

from envoy.admin.mapper.log import CalculationLogMapper
from envoy.server.model.log import CalculationLog, PowerFlowLog, PowerForecastLog, PowerTargetLog, WeatherForecastLog


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
            PowerFlowLog, original_pf, actual_pf, ignored_properties=set(["power_flow_log_id", "calculation_log_id"])
        )

    # Assert PowerTarget
    assert len(actual.power_target_logs) == len(original.power_target_logs)
    for actual_pt, original_pt in zip(actual.power_target_logs, original.power_target_logs):
        assert_class_instance_equality(
            PowerTargetLog,
            original_pt,
            actual_pt,
            ignored_properties=set(["power_target_log_id", "calculation_log_id"]),
        )

    # Assert PowerForecast
    assert len(actual.power_forecast_logs) == len(original.power_forecast_logs)
    for actual_pfore, original_pfore in zip(actual.power_forecast_logs, original.power_forecast_logs):
        assert_class_instance_equality(
            PowerForecastLog,
            original_pfore,
            actual_pfore,
            ignored_properties=set(["power_forecast_log_id", "calculation_log_id"]),
        )

    # Assert WeatherForecast
    assert len(actual.weather_forecast_logs) == len(original.weather_forecast_logs)
    for actual_w, original_w in zip(actual.weather_forecast_logs, original.weather_forecast_logs):
        assert_class_instance_equality(
            WeatherForecastLog,
            original_w,
            actual_w,
            ignored_properties=set(["weather_forecast_log_id", "calculation_log_id"]),
        )
