from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from envoy.admin.crud.log import select_calculation_log_by_id, select_most_recent_calculation_log_for_interval_start
from envoy.server.model.log import CalculationLog, PowerFlowLog, PowerForecastLog, PowerTargetLog, WeatherForecastLog
from tests.assert_time import assert_datetime_equal
from tests.postgres_testing import generate_async_session


@pytest.mark.parametrize("id", [0, -1, 4])
@pytest.mark.anyio
async def test_select_calculation_log_by_id_missing(pg_base_config, id: int):
    """Does an invalid ID generate None without error"""
    async with generate_async_session(pg_base_config) as session:
        assert await select_calculation_log_by_id(session, id) is None


@pytest.mark.anyio
async def test_select_calculation_log_by_id(pg_base_config):
    """Tests that the correct log with child relations are returned"""
    async with generate_async_session(pg_base_config) as session:

        # Calculation log 1 has no children - sanity check the contents
        calc_log_1 = await select_calculation_log_by_id(session, 1)
        assert calc_log_1 is not None and isinstance(calc_log_1, CalculationLog)
        assert calc_log_1.external_id == "external-id-1"
        assert_datetime_equal(
            calc_log_1.calculation_interval_start, datetime(2024, 1, 31, 1, 2, 3, tzinfo=timezone.utc)
        )
        assert calc_log_1.calculation_interval_duration_seconds == 86401
        assert len(calc_log_1.weather_forecast_logs) == 0
        assert len(calc_log_1.power_flow_logs) == 0
        assert len(calc_log_1.power_target_logs) == 0
        assert len(calc_log_1.power_forecast_logs) == 0

        # Calculation log 2 has children - sanity check the contents
        calc_log_2 = await select_calculation_log_by_id(session, 2)
        assert calc_log_2 is not None and isinstance(calc_log_2, CalculationLog)
        assert calc_log_2.external_id == "external-id-2"
        assert_datetime_equal(
            calc_log_2.calculation_interval_start, datetime(2024, 1, 31, 1, 2, 3, tzinfo=timezone.utc)
        )
        assert calc_log_2.calculation_interval_duration_seconds == 86402
        assert len(calc_log_2.weather_forecast_logs) == 1
        assert len(calc_log_2.power_flow_logs) == 2
        assert len(calc_log_2.power_target_logs) == 2
        assert len(calc_log_2.power_forecast_logs) == 2
        assert all(isinstance(e, WeatherForecastLog) for e in calc_log_2.weather_forecast_logs)
        assert all(isinstance(e, PowerFlowLog) for e in calc_log_2.power_flow_logs)
        assert all(isinstance(e, PowerTargetLog) for e in calc_log_2.power_target_logs)
        assert all(isinstance(e, PowerForecastLog) for e in calc_log_2.power_forecast_logs)
        assert [e.weather_forecast_log_id for e in calc_log_2.weather_forecast_logs] == [1]
        assert [e.power_flow_log_id for e in calc_log_2.power_flow_logs] == [1, 2]
        assert [e.power_target_log_id for e in calc_log_2.power_target_logs] == [1, 2]
        assert [e.power_forecast_log_id for e in calc_log_2.power_forecast_logs] == [1, 2]


@pytest.mark.parametrize(
    "interval_start",
    [
        datetime(2016, 1, 2),  # Naive datetime
        datetime(2024, 1, 31, 1, 2, 3, tzinfo=ZoneInfo("Australia/Perth")),  # wrong timezone
        datetime(2024, 1, 31, 0, 0, 0, tzinfo=timezone.utc),  # same date - wrong time
    ],
)
@pytest.mark.anyio
async def test_select_most_recent_calculation_log_for_interval_start_missing(pg_base_config, interval_start: datetime):
    """Does an invalid date generate None without error"""
    async with generate_async_session(pg_base_config) as session:
        assert await select_most_recent_calculation_log_for_interval_start(session, interval_start) is None


@pytest.mark.anyio
async def test_select_most_recent_calculation_log_for_interval_start(pg_base_config):
    """Tests that the correct log with child relations are returned"""

    # This interval has 2 calculation logs - only the most recent (calc_2) will be returned
    interval_start = datetime(2024, 1, 31, 1, 2, 3, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        calc_log_2 = await select_most_recent_calculation_log_for_interval_start(session, interval_start)
        assert calc_log_2 is not None and isinstance(calc_log_2, CalculationLog)
        assert calc_log_2.external_id == "external-id-2"
        assert_datetime_equal(calc_log_2.calculation_interval_start, interval_start)
        assert calc_log_2.calculation_interval_duration_seconds == 86402
        assert len(calc_log_2.weather_forecast_logs) == 1
        assert len(calc_log_2.power_flow_logs) == 2
        assert len(calc_log_2.power_target_logs) == 2
        assert len(calc_log_2.power_forecast_logs) == 2
        assert all(isinstance(e, WeatherForecastLog) for e in calc_log_2.weather_forecast_logs)
        assert all(isinstance(e, PowerFlowLog) for e in calc_log_2.power_flow_logs)
        assert all(isinstance(e, PowerTargetLog) for e in calc_log_2.power_target_logs)
        assert all(isinstance(e, PowerForecastLog) for e in calc_log_2.power_forecast_logs)
        assert [e.weather_forecast_log_id for e in calc_log_2.weather_forecast_logs] == [1]
        assert [e.power_flow_log_id for e in calc_log_2.power_flow_logs] == [1, 2]
        assert [e.power_target_log_id for e in calc_log_2.power_target_logs] == [1, 2]
        assert [e.power_forecast_log_id for e in calc_log_2.power_forecast_logs] == [1, 2]
