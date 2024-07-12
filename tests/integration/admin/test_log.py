from datetime import datetime, timezone
from http import HTTPStatus
from itertools import product
from typing import Optional

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.log import (
    CalculationLogListResponse,
    CalculationLogRequest,
    CalculationLogResponse,
    PowerFlowLog,
    PowerForecastLog,
    PowerTargetLog,
    WeatherForecastLog,
)
from envoy_schema.admin.schema.uri import CalculationLogCreateUri, CalculationLogsForPeriod, CalculationLogUri
from httpx import AsyncClient

from envoy.server.api.response import LOCATION_HEADER_NAME


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


@pytest.mark.parametrize(
    "period_start, period_end, start, limit, expected_ids, expected_count",
    [
        (
            "2023-09-08T00:00+10:00",
            "2023-09-09T00:00+10:00",
            None,
            None,
            [],
            0,
        ),  # Too early
        (
            "2023-09-11T00:00+10:00",
            "2023-09-12T00:00+10:00",
            0,
            None,
            [],
            0,
        ),  # Too late
        (
            "2023-09-08T00:00+10:00",
            "2023-09-12T00:00+10:00",
            None,
            5,
            [4, 5, 6, 7],
            4,
        ),  # Perfectly match 2 day Range
        (
            "2023-09-08T00:00+10:00",
            "2023-09-12T00:00+10:00",
            1,
            2,
            [5, 6],
            4,
        ),  # Paging
    ],
)
@pytest.mark.anyio
async def test_get_calculation_logs_for_period(
    pg_billing_data,
    admin_client_auth: AsyncClient,
    period_start: str,
    period_end: str,
    start: Optional[int],
    limit: Optional[int],
    expected_ids: list[int],
    expected_count: int,
):
    uri = CalculationLogsForPeriod.format(period_start=period_start, period_end=period_end) + "?"
    if start is not None:
        uri += f"&start={start}"
    if limit is not None:
        uri += f"&limit={limit}"
    resp = await admin_client_auth.get(uri)
    assert resp.status_code == HTTPStatus.OK

    log_list = CalculationLogListResponse.model_validate_json(resp.content)
    assert log_list.total_calculation_logs == expected_count
    assert log_list.start == (start if start is not None else 0)
    assert log_list.limit == (limit if limit is not None else 100)
    assert all([isinstance(cl, CalculationLogResponse) for cl in log_list.calculation_logs])
    assert all([cl.power_flow_logs == [] for cl in log_list.calculation_logs]), "No child logs in list endpoint"
    assert all([cl.power_forecast_logs == [] for cl in log_list.calculation_logs]), "No child logs in list endpoint"
    assert all([cl.power_target_logs == [] for cl in log_list.calculation_logs]), "No child logs in list endpoint"
    assert all([cl.weather_forecast_logs == [] for cl in log_list.calculation_logs]), "No child logs in list endpoint"

    assert [cl.calculation_log_id for cl in log_list.calculation_logs] == expected_ids
