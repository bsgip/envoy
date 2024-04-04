from datetime import datetime, timezone
from http import HTTPStatus
from itertools import product

import pytest
from envoy_schema.admin.schema.log import (
    CalculationLogRequest,
    CalculationLogResponse,
    PowerFlowLog,
    PowerForecastLog,
    PowerTargetLog,
    WeatherForecastLog,
)
from envoy_schema.admin.schema.uri import CalculationLogCreateUri, CalculationLogForDateUri, CalculationLogUri
from httpx import AsyncClient

from envoy.server.api.response import LOCATION_HEADER_NAME
from tests.assert_time import assert_datetime_equal, assert_nowish
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


def assert_calc_log_2(calc_log_2: CalculationLogResponse) -> None:
    assert calc_log_2 is not None and isinstance(calc_log_2, CalculationLogResponse)
    assert calc_log_2.external_id == "external-id-2"
    assert_datetime_equal(calc_log_2.calculation_interval_start, datetime(2024, 1, 31, 1, 2, 3, tzinfo=timezone.utc))
    assert calc_log_2.calculation_interval_duration_seconds == 86402
    assert len(calc_log_2.weather_forecast_logs) == 1
    assert len(calc_log_2.power_flow_logs) == 2
    assert len(calc_log_2.power_target_logs) == 2
    assert len(calc_log_2.power_forecast_logs) == 2
    assert all(isinstance(e, WeatherForecastLog) for e in calc_log_2.weather_forecast_logs)
    assert all(isinstance(e, PowerFlowLog) for e in calc_log_2.power_flow_logs)
    assert all(isinstance(e, PowerTargetLog) for e in calc_log_2.power_target_logs)
    assert all(isinstance(e, PowerForecastLog) for e in calc_log_2.power_forecast_logs)
    assert [e.air_temperature_degrees_c for e in calc_log_2.weather_forecast_logs] == [11.5]
    assert [e.solve_name for e in calc_log_2.power_flow_logs] == ["solve-1", "solve-2"]
    assert [e.target_active_power_watts for e in calc_log_2.power_target_logs] == [11, 21]
    assert [e.active_power_watts for e in calc_log_2.power_forecast_logs] == [111, 211]


@pytest.mark.anyio
async def test_get_calculation_log_by_id(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(CalculationLogUri.format(calculation_log_id=2))
    assert resp.status_code == HTTPStatus.OK

    calc_log_2 = CalculationLogResponse.model_validate_json(resp.content)
    assert_calc_log_2(calc_log_2)


@pytest.mark.anyio
async def test_get_calculation_log_by_id_missing(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(CalculationLogUri.format(calculation_log_id=4))
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.anyio
async def test_get_calculation_log_by_interval(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(
        CalculationLogForDateUri.format(calculation_interval_start="2024-01-31T01:02:03Z")
    )
    assert resp.status_code == HTTPStatus.OK

    calc_log_2 = CalculationLogResponse.model_validate_json(resp.content)
    assert_calc_log_2(calc_log_2)


@pytest.mark.anyio
async def test_get_calculation_log_by_interval_missing(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(
        CalculationLogForDateUri.format(calculation_interval_start="2024-01-31T00:00:00Z")
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("optional_is_none, include_children", product([True, False], [True, False]))
@pytest.mark.anyio
async def test_calculation_log_roundtrip_with_children(
    admin_client_auth: AsyncClient, optional_is_none: bool, include_children: bool
):
    """Creates a calculation log - sends it off, pulls it back and ensures the contents is all still the same"""
    wf_log = generate_class_instance(WeatherForecastLog, optional_is_none=optional_is_none)
    pflow_log = generate_class_instance(PowerFlowLog, optional_is_none=optional_is_none)
    pt_log = generate_class_instance(PowerTargetLog, optional_is_none=optional_is_none)
    pfore_log = generate_class_instance(PowerForecastLog, optional_is_none=optional_is_none)

    calc_log: CalculationLogRequest = generate_class_instance(CalculationLogRequest, optional_is_none=optional_is_none)
    if include_children:
        calc_log.weather_forecast_logs = [wf_log]
        calc_log.power_flow_logs = [pflow_log]
        calc_log.power_forecast_logs = [pfore_log]
        calc_log.power_target_logs = [pt_log]

    # Upload the log
    resp = await admin_client_auth.post(CalculationLogCreateUri, content=calc_log.model_dump_json())
    assert resp.status_code == HTTPStatus.CREATED
    uri = resp.headers[LOCATION_HEADER_NAME]
    assert uri

    # download the log
    resp = await admin_client_auth.get(uri)
    assert resp.status_code == HTTPStatus.OK

    # Validate the response
    returned_log = CalculationLogResponse.model_validate_json(resp.content)
    assert_class_instance_equality(CalculationLogRequest, calc_log, returned_log)
    assert_nowish(returned_log.created_time)
    if include_children:
        assert len(returned_log.weather_forecast_logs) == 1
        assert len(returned_log.power_flow_logs) == 1
        assert len(returned_log.power_forecast_logs) == 1
        assert len(returned_log.power_target_logs) == 1

        assert_class_instance_equality(WeatherForecastLog, wf_log, returned_log.weather_forecast_logs[0])
        assert_class_instance_equality(PowerFlowLog, pflow_log, returned_log.power_flow_logs[0])
        assert_class_instance_equality(PowerTargetLog, pt_log, returned_log.power_target_logs[0])
        assert_class_instance_equality(PowerForecastLog, pfore_log, returned_log.power_forecast_logs[0])
    else:
        assert len(returned_log.weather_forecast_logs) == 0
        assert len(returned_log.power_flow_logs) == 0
        assert len(returned_log.power_forecast_logs) == 0
        assert len(returned_log.power_target_logs) == 0
