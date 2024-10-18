from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_datetime_equal
from assertical.asserts.type import assert_iterable_type
from assertical.fixtures.postgres import generate_async_session

from envoy.admin.crud.log import (
    count_calculation_logs_for_period,
    select_calculation_log_by_id,
    select_calculation_logs_for_period,
)
from envoy.server.model.log import CalculationLog, CalculationLogVariableMetadata, CalculationLogVariableValue


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
        assert_datetime_equal(calc_log_1.calculation_range_start, datetime(2024, 1, 31, 1, 2, 3, tzinfo=timezone.utc))
        assert calc_log_1.calculation_range_duration_seconds == 86401
        assert len(calc_log_1.variable_metadata) == 0
        assert len(calc_log_1.variable_values) == 0

        # Calculation log 2 has children - sanity check the contents
        calc_log_2 = await select_calculation_log_by_id(session, 2)
        assert calc_log_2 is not None and isinstance(calc_log_2, CalculationLog)
        assert calc_log_2.external_id == "external-id-2"
        assert_datetime_equal(calc_log_2.calculation_range_start, datetime(2024, 1, 31, 1, 2, 3, tzinfo=timezone.utc))
        assert calc_log_2.calculation_range_duration_seconds == 86402
        assert_iterable_type(CalculationLogVariableMetadata, calc_log_2.variable_metadata, count=3)
        assert_iterable_type(CalculationLogVariableValue, calc_log_2.variable_values, count=6)

        # There should be a defined order on the returned calculation log variable values
        # ON CalculationLogID -> Variable ID -> Site ID -> Interval Period
        assert [3.3, 2.2, 4.4, -5.5, 0, 1.1] == [e.value for e in calc_log_2.variable_values]


AEST = ZoneInfo("Australia/Brisbane")


@pytest.mark.parametrize(
    "period_start, period_end, start, limit, expected_ids, expected_count",
    [
        (
            datetime(2023, 9, 8, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 9, 0, 0, 0, tzinfo=AEST),
            0,
            100,
            [],
            0,
        ),  # Too early
        (
            datetime(2023, 9, 11, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 12, 0, 0, 0, tzinfo=AEST),
            0,
            100,
            [],
            0,
        ),  # Too late
        (
            datetime(2023, 9, 10, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 11, 0, 0, 0, tzinfo=AEST),
            0,
            100,
            [4, 5, 6],
            3,
        ),  # Perfectly match 1 day range
        (
            datetime(2023, 9, 9, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 11, 0, 0, 0, tzinfo=AEST),
            0,
            100,
            [4, 5, 6, 7],
            4,
        ),  # Perfectly match 2 day Range
        (
            datetime(2023, 9, 8, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 12, 0, 0, 0, tzinfo=AEST),
            0,
            100,
            [4, 5, 6, 7],
            4,
        ),  # Full encapsulation of Range
        (
            datetime(2023, 9, 10, 12, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 11, 12, 0, 0, tzinfo=AEST),
            0,
            100,
            [4, 5],
            2,
        ),  # Intersect (but 6 will not match as it only has a 5 minute period)
        (
            datetime(2023, 9, 10, 0, 0, 10, tzinfo=AEST),
            datetime(2023, 9, 10, 10, 0, 0, tzinfo=AEST),
            0,
            100,
            [4, 5, 6],
            3,
        ),  # Encapsulated by the logs
        (
            datetime(2023, 9, 9, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 11, 0, 0, 0, tzinfo=AEST),
            0,
            2,
            [4, 5],
            4,
        ),  # Paging
        (
            datetime(2023, 9, 9, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 11, 0, 0, 0, tzinfo=AEST),
            2,
            2,
            [6, 7],
            4,
        ),  # Paging
        (
            datetime(2023, 9, 9, 0, 0, 0, tzinfo=AEST),
            datetime(2023, 9, 11, 0, 0, 0, tzinfo=AEST),
            4,
            2,
            [],
            4,
        ),  # Paging
    ],
)
@pytest.mark.anyio
async def test_select_calculation_logs_for_period(
    pg_billing_data,
    period_start: datetime,
    period_end: datetime,
    start: int,
    limit: int,
    expected_ids: list[int],
    expected_count: int,
):
    """Tests that the correct log with child relations are returned"""

    async with generate_async_session(pg_billing_data) as session:
        calc_logs = await select_calculation_logs_for_period(session, period_start, period_end, start, limit)
        assert all([isinstance(log, CalculationLog) for log in calc_logs])
        assert [log.calculation_log_id for log in calc_logs] == expected_ids

        assert await count_calculation_logs_for_period(session, period_start, period_end) == expected_count
