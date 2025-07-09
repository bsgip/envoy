from datetime import datetime

import pytest
from assertical.fixtures.postgres import generate_async_session
from zoneinfo import ZoneInfo
from envoy.admin.crud.site_reading import (
    count_site_readings_for_site_and_time,
    select_csip_aus_site_type_ids,
    select_site_readings_for_site_and_time,
)
from envoy_schema.server.schema.sep2.types import UomType

TZ = ZoneInfo("Australia/Brisbane")


@pytest.mark.parametrize(
    "aggregator_id, site_id, uom, expected_site_type_ids",
    [
        # Site 1, UOM 38 (ACTIVEPOWER):
        # - ID 1: Site 1, Agg 1, UOM 38, DQ 2 (AVERAGE), Kind 37 (POWER) ✓
        # - ID 3: Site 1, Agg 1, UOM 38, DQ 8 (not AVERAGE/NOT_APPLICABLE) ✗
        (1, 1, UomType.REAL_POWER_WATT, [1]),
        # Site 2, UOM 38:
        # - ID 4: Site 2, Agg 1, UOM 38, DQ 9, Kind 12 (not POWER/NOT_APPLICABLE) ✗
        (1, 2, UomType.REAL_POWER_WATT, []),
        # Test CSIP units that don't exist in the base config data
        (1, 1, UomType.REACTIVE_POWER_VAR, []),
        (1, 1, UomType.FREQUENCY_HZ, []),
        (1, 1, UomType.VOLTAGE, []),
        # Edge cases
        (999, 1, UomType.REAL_POWER_WATT, []),  # Non-existent aggregator
        (1, 999, UomType.REAL_POWER_WATT, []),  # Non-existent site
        (1, 1, UomType.VOLUME_US_GALLON_PER_HOUR, []),  # Non-valid UOM (for this function)
    ],
)
@pytest.mark.anyio
async def test_select_csip_aus_site_type_ids(
    pg_base_config, aggregator_id: int, site_id: int, uom: int, expected_site_type_ids: list[int]
):
    async with generate_async_session(pg_base_config) as session:
        site_type_ids = await select_csip_aus_site_type_ids(session, aggregator_id, site_id, uom)
        assert list(site_type_ids) == expected_site_type_ids


@pytest.mark.parametrize(
    "site_type_ids, start_time, end_time, expected_count",
    [
        # site_reading_type_id = 1 has 2 readings in June 2022
        ([1], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 2),
        # site_reading_type_id = 2 has 1 reading in June 2022
        ([2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 1),
        # Multiple type IDs
        ([1, 2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 3),
        # Broader date range but no extra readings
        ([1], datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ), 2),
        ([1, 2], datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ), 3),
        # Narrow time
        ([1], datetime(2022, 6, 7, 0, 0, tzinfo=TZ), datetime(2022, 6, 7, 1, 30, tzinfo=TZ), 1),
        # No data cases
        ([999], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0),  # Non-existent type
        ([], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0),  # Empty type list
        ([1], datetime(2023, 1, 1, tzinfo=TZ), datetime(2023, 12, 31, tzinfo=TZ), 0),  # No data in range
    ],
)
@pytest.mark.anyio
async def test_count_site_readings_for_site_and_time(
    pg_base_config, site_type_ids: list[int], start_time: datetime, end_time: datetime, expected_count: int
):
    async with generate_async_session(pg_base_config) as session:
        actual_count = await count_site_readings_for_site_and_time(session, site_type_ids, start_time, end_time)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "site_type_ids, start_time, end_time, start, limit, expected_count",
    [
        # 2 readings for type 1
        ([1], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 500, 2),
        # Single reading for type 2
        ([2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 500, 1),
        # Multiple types - 3 total readings
        ([1, 2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 500, 3),
        # Pagination tests with type 1 (2 readings)
        ([1], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 1, 1),  # First page
        ([1], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 1, 1, 1),  # Second page
        ([1], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 2, 1, 0),  # Third page (empty)
        # Pagination with multiple types (3 readings total)
        ([1, 2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 2, 2),
        ([1, 2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 2, 2, 1),
        # Time filtering - narrow windows (readings at 01:00 and 02:00 Brisbane time)
        ([1], datetime(2022, 6, 7, 0, 0, tzinfo=TZ), datetime(2022, 6, 7, 1, 30, tzinfo=TZ), 0, 500, 1),
        ([1], datetime(2022, 6, 7, 1, 30, tzinfo=TZ), datetime(2022, 6, 7, 3, 0, tzinfo=TZ), 0, 500, 1),
        # Edge cases
        ([999], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 500, 0),  # Non-existent type
        ([], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 500, 0),  # Empty type list
        ([1], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ), 0, 0, 0),  # Zero limit
    ],
)
@pytest.mark.anyio
async def test_select_site_readings_for_site_and_time(
    pg_base_config,
    site_type_ids: list[int],
    start_time: datetime,
    end_time: datetime,
    start: int,
    limit: int,
    expected_count: int,
):
    async with generate_async_session(pg_base_config) as session:
        readings = await select_site_readings_for_site_and_time(
            session, site_type_ids, start_time, end_time, start, limit
        )

        assert len(readings) == expected_count

        # Test relationship loading
        if len(readings) > 0:
            for reading in readings:
                assert reading.site_reading_type is not None
                assert reading.site_reading_type.site_reading_type_id in site_type_ids

        # Test time range filtering (< end_time, not <=)
        for reading in readings:
            assert start_time <= reading.time_period_start < end_time

        # Test ordering (readings should be ordered by time_period_start ASC)
        if len(readings) > 1:
            for i in range(1, len(readings)):
                assert readings[i - 1].time_period_start <= readings[i].time_period_start


@pytest.mark.anyio
async def test_count_and_select_consistency(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        test_cases = [
            ([1], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ)),
            ([2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ)),
            ([1, 2], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ)),
            ([4], datetime(2022, 6, 1, tzinfo=TZ), datetime(2022, 6, 30, tzinfo=TZ)),
        ]

        for site_type_ids, start_time, end_time in test_cases:
            count = await count_site_readings_for_site_and_time(session, site_type_ids, start_time, end_time)
            readings = await select_site_readings_for_site_and_time(
                session, site_type_ids, start_time, end_time, 0, 500
            )
            assert count == len(
                readings
            ), f"Count mismatch for site_type_ids {site_type_ids}: expected {count}, got {len(readings)}"


@pytest.mark.anyio
async def test_empty_database(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        count = await count_site_readings_for_site_and_time(
            session, [1], datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ)
        )
        assert count == 0

        readings = await select_site_readings_for_site_and_time(
            session, [1], datetime(2022, 1, 1, tzinfo=TZ), datetime(2022, 12, 31, tzinfo=TZ)
        )
        assert len(readings) == 0
