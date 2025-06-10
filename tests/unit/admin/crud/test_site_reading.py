from datetime import datetime, timezone

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session

from envoy.admin.crud.site_reading import (
    count_site_readings_for_site_and_time,
    select_site_readings_for_site_and_time,
)
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from assertical.fake.generator import generate_class_instance


@pytest.mark.parametrize(
    "site_id, start_time, end_time, expected_count",
    [
        # Basic functionality tests
        (1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 3),
        (2, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 2),
        # Time range filtering
        (1, datetime(2022, 6, 1, tzinfo=timezone.utc), datetime(2022, 8, 31, tzinfo=timezone.utc), 1),
        # Edge cases
        (
            999,
            datetime(2022, 1, 1, tzinfo=timezone.utc),
            datetime(2022, 12, 31, tzinfo=timezone.utc),
            0,
        ),  # Non-existent site
        (
            1,
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 12, 31, tzinfo=timezone.utc),
            0,
        ),  # No data in range
    ],
)
@pytest.mark.anyio
async def test_count_site_readings_for_site_and_time(
    pg_base_config, site_id: int, start_time: datetime, end_time: datetime, expected_count: int
):
    """Test counting site readings with various parameters"""
    async with generate_async_session(pg_base_config) as session:
        # Create test data
        await _create_test_site_reading_data(session)
        await session.commit()

        actual_count = await count_site_readings_for_site_and_time(session, site_id, start_time, end_time)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "site_id, start_time, end_time, start, limit, expected_count",
    [
        # Basic functionality
        (1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 0, 1000, 3),
        (2, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 0, 1000, 2),
        # Pagination
        (1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 0, 2, 2),
        (1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 1, 2, 2),
        # Time filtering
        (1, datetime(2022, 6, 1, tzinfo=timezone.utc), datetime(2022, 8, 31, tzinfo=timezone.utc), 0, 1000, 1),
        # Edge cases
        (999, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 0, 1000, 0),
        (1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc), 0, 0, 0),
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
    """Test selecting site readings with various parameters"""
    async with generate_async_session(pg_base_config) as session:
        # Create test data
        await _create_test_site_reading_data(session)
        await session.commit()

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

        # Test ordering
        if len(readings) > 1:
            for i in range(1, len(readings)):
                assert readings[i - 1].time_period_start <= readings[i].time_period_start


@pytest.mark.anyio
async def test_count_and_select_consistency(pg_base_config):
    """Test that count and select return consistent results"""
    async with generate_async_session(pg_base_config) as session:
        # Create test data
        await _create_test_site_reading_data(session)
        await session.commit()

        test_cases = [
            (1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc)),
            (2, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc)),
        ]

        for site_id, start_time, end_time in test_cases:
            count = await count_site_readings_for_site_and_time(session, site_id, start_time, end_time)

            readings = await select_site_readings_for_site_and_time(session, site_id, start_time, end_time, 0, 1000)

            assert count == len(readings), f"Count mismatch for site {site_id}"


@pytest.mark.anyio
async def test_empty_database(pg_empty_config):
    """Test behavior with empty database"""
    async with generate_async_session(pg_empty_config) as session:
        count = await count_site_readings_for_site_and_time(
            session, 1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc)
        )
        assert count == 0

        readings = await select_site_readings_for_site_and_time(
            session, 1, datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2022, 12, 31, tzinfo=timezone.utc)
        )
        assert len(readings) == 0


async def _create_test_site_reading_data(session):
    """Create minimal test data for site reading tests"""

    # Create SiteReadingType records using the base config sites (assumes sites 1, 2 exist)
    srt1 = generate_class_instance(SiteReadingType, aggregator_id=1, site_id=1, uom=38, kind=37)
    srt2 = generate_class_instance(SiteReadingType, aggregator_id=1, site_id=2, uom=38, kind=37)
    session.add(srt1)
    session.add(srt2)
    await session.flush()  # Get the IDs

    # Create SiteReading records
    readings = [
        # Site 1 readings
        SiteReading(
            site_reading_type_id=srt1.site_reading_type_id,
            time_period_start=datetime(2022, 2, 15, 12, 0, 0, tzinfo=timezone.utc),
            time_period_seconds=3600,
            value=1000,
            local_id=1,
            quality_flags=0,
            created_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
            changed_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
        ),
        SiteReading(
            site_reading_type_id=srt1.site_reading_type_id,
            time_period_start=datetime(2022, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
            time_period_seconds=3600,
            value=1500,
            local_id=2,
            quality_flags=0,
            created_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
            changed_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
        ),
        SiteReading(
            site_reading_type_id=srt1.site_reading_type_id,
            time_period_start=datetime(2022, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
            time_period_seconds=3600,
            value=1900,
            local_id=3,
            quality_flags=0,
            created_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
            changed_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
        ),
        # Site 2 readings
        SiteReading(
            site_reading_type_id=srt2.site_reading_type_id,
            time_period_start=datetime(2022, 3, 20, 14, 0, 0, tzinfo=timezone.utc),
            time_period_seconds=3600,
            value=2000,
            local_id=4,
            quality_flags=0,
            created_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
            changed_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
        ),
        SiteReading(
            site_reading_type_id=srt2.site_reading_type_id,
            time_period_start=datetime(2022, 9, 20, 14, 0, 0, tzinfo=timezone.utc),
            time_period_seconds=3600,
            value=2500,
            local_id=5,
            quality_flags=0,
            created_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
            changed_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
        ),
    ]

    for reading in readings:
        session.add(reading)
