from datetime import datetime

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session
from zoneinfo import ZoneInfo
from envoy.admin.crud.site_reading import (
    count_site_readings_for_site_and_time,
    select_site_readings_for_site_and_time,
)
from envoy.server.model.site_reading import SiteReading

TZ = ZoneInfo("Australia/Brisbane")


@pytest.mark.parametrize(
    "site_id, start_time, end_time, expected_count",
    [
        # Basic functionality tests using base config data (2022-06-07 readings)
        (1, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 3),
        (2, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 1),
        # Broader time range that includes the base config data
        (1, datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ), 3),
        (2, datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ), 1),
        # Precise time range filtering - only readings at 01:00 for site 1 (2 readings)
        (1, datetime(2022, 6, 7, 1, 0, tzinfo=TZ), datetime(2022, 6, 7, 1, 30, tzinfo=TZ), 2),
        # Precise time range filtering - only readings at 02:00 for site 1 (1 reading)
        (1, datetime(2022, 6, 7, 2, 0, tzinfo=TZ), datetime(2022, 6, 7, 2, 30, tzinfo=TZ), 1),
        # Edge cases
        (
            999,
            datetime(2022, 6, 1, tzinfo=TZ),
            datetime(2022, 6, 30, tzinfo=TZ),
            0,
        ),  # Non-existent site
        (
            1,
            datetime(2023, 1, 1, tzinfo=TZ),
            datetime(2023, 12, 31, tzinfo=TZ),
            0,
        ),  # No data in range
    ],
)
@pytest.mark.anyio
async def test_count_site_readings_for_site_and_time(
    pg_base_config, site_id: int, start_time: datetime, end_time: datetime, expected_count: int
):
    """Test counting site readings with various parameters using base config data"""
    async with generate_async_session(pg_base_config) as session:
        actual_count = await count_site_readings_for_site_and_time(session, site_id, start_time, end_time)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "site_id, start_time, end_time, start, limit, expected_count",
    [
        # Basic functionality using base config data
        (1, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 1000, 3),
        (2, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 1000, 1),
        # Pagination tests
        (1, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 2, 2),
        (1, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 1, 2, 2),
        (1, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 2, 2, 1),
        # Time filtering - precise hour ranges
        (
            1,
            datetime(2022, 6, 7, 1, 0, tzinfo=TZ),
            datetime(2022, 6, 7, 1, 30, tzinfo=TZ),
            0,
            1000,
            2,
        ),
        (
            1,
            datetime(2022, 6, 7, 2, 0, tzinfo=TZ),
            datetime(2022, 6, 7, 2, 30, tzinfo=TZ),
            0,
            1000,
            1,
        ),
        # Edge cases
        (999, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 1000, 0),
        (1, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 0, 0),
    ],
)
@pytest.mark.anyio
async def test_select_site_readings_for_site_and_time(
    pg_base_config,
    site_id: int,
    start_time: datetime,
    end_time: datetime,
    start: int,
    limit: int,
    expected_count: int,
):
    """Test selecting site readings with various parameters using base config data"""
    async with generate_async_session(pg_base_config) as session:
        readings = await select_site_readings_for_site_and_time(session, site_id, start_time, end_time, start, limit)

        # Basic assertions
        assert_list_type(SiteReading, readings, count=expected_count)

        # Test relationship loading
        if len(readings) > 0:
            for reading in readings:
                assert reading.site_reading_type is not None
                assert reading.site_reading_type.site_id == site_id

        # Test time range filtering
        for reading in readings:
            assert start_time <= reading.time_period_start <= end_time

        # Test ordering (readings should be ordered by time_period_start ASC)
        if len(readings) > 1:
            for i in range(1, len(readings)):
                assert readings[i - 1].time_period_start <= readings[i].time_period_start


@pytest.mark.anyio
async def test_count_and_select_consistency(pg_base_config):
    """Test that count and select return consistent results using base config data"""
    async with generate_async_session(pg_base_config) as session:
        test_cases = [
            (1, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ)),
            (2, datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ)),
            # Test broader ranges
            (1, datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ)),
            (2, datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ)),
        ]

        for site_id, start_time, end_time in test_cases:
            count = await count_site_readings_for_site_and_time(session, site_id, start_time, end_time)

            readings = await select_site_readings_for_site_and_time(session, site_id, start_time, end_time, 0, 1000)

            assert count == len(readings), f"Count mismatch for site {site_id}: expected {count}, got {len(readings)}"


@pytest.mark.anyio
async def test_empty_database(pg_empty_config):
    """Test behavior with empty database"""
    async with generate_async_session(pg_empty_config) as session:
        count = await count_site_readings_for_site_and_time(
            session, 1, datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ)
        )
        assert count == 0

        readings = await select_site_readings_for_site_and_time(
            session, 1, datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ)
        )
        assert len(readings) == 0
