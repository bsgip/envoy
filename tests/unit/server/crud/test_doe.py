from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_datetime_equal
from assertical.fixtures.postgres import generate_async_session

from envoy.server.crud.doe import (
    count_does,
    count_does_at_timestamp,
    count_does_for_day,
    select_does,
    select_does_at_timestamp,
    select_does_for_day,
)
from envoy.server.model.doe import DynamicOperatingEnvelope as DOE


def assert_doe_for_id(
    expected_doe_id: Optional[int],
    expected_site_id: Optional[int],
    expected_datetime: Optional[datetime],
    expected_tz: Optional[str],
    actual_rate: Optional[DOE],
    check_duration_seconds: bool = True,
):
    """Asserts the supplied doe matches the expected values for a doe with that id. These values are based
    purely on the data patterns in base_config.sql"""
    if expected_doe_id is None:
        assert actual_rate is None
    else:
        assert actual_rate
        assert actual_rate.dynamic_operating_envelope_id == expected_doe_id
        assert expected_site_id is None or actual_rate.site_id == expected_site_id
        if check_duration_seconds:
            assert actual_rate.duration_seconds == 10 * expected_doe_id + expected_doe_id
        assert actual_rate.import_limit_active_watts == Decimal(f"{expected_doe_id}.11")
        assert actual_rate.export_limit_watts == Decimal(f"-{expected_doe_id}.22")
        if expected_datetime:
            tz = ZoneInfo(expected_tz)
            expected_in_local = datetime(
                expected_datetime.year,
                expected_datetime.month,
                expected_datetime.day,
                expected_datetime.hour,
                expected_datetime.minute,
                expected_datetime.second,
                tzinfo=tz,
            )
            assert_datetime_equal(actual_rate.start_time, expected_in_local)
            assert actual_rate.start_time.tzname() == tz.tzname(
                actual_rate.start_time
            ), "Start time should be returned in local time"


@pytest.mark.parametrize(
    "expected_ids, start, after, limit",
    [
        ([1, 2, 4], 0, datetime.min, 99),
        ([1], 0, datetime.min, 1),
        ([2, 4], 1, datetime.min, 99),
        ([2], 1, datetime.min, 1),
        ([4], 2, datetime.min, 99),
        ([], 3, datetime.min, 99),
        ([], 0, datetime.min, 0),
        ([2, 4], 0, datetime(2022, 5, 6, 12, 22, 32, tzinfo=timezone.utc), 99),
        ([4], 0, datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc), 99),
    ],
)
@pytest.mark.anyio
async def test_select_doe_pagination(pg_base_config, expected_ids: list[int], start: int, after: datetime, limit: int):
    """Tests out the basic pagination features"""
    async with generate_async_session(pg_base_config) as session:
        rates = await select_does(session, 1, 1, start, after, limit)
        assert len(rates) == len(expected_ids)
        for id, rate in zip(expected_ids, rates):
            assert_doe_for_id(id, 1, None, None, rate)


@pytest.mark.parametrize(
    "expected_id_and_starts, agg_id, site_id",
    [
        ([(1, datetime(2022, 5, 7, 1, 2)), (2, datetime(2022, 5, 7, 3, 4)), (4, datetime(2022, 5, 8, 1, 2))], 1, 1),
        ([(3, datetime(2022, 5, 7, 1, 2))], 1, 2),
        ([], 2, 1),
        ([], 1, 3),
        (
            [
                (3, datetime(2022, 5, 7, 1, 2)),  # For site #2
                (1, datetime(2022, 5, 7, 1, 2)),  # Site #1
                (2, datetime(2022, 5, 7, 3, 4)),  # Site #1
                (4, datetime(2022, 5, 8, 1, 2)),  # Site #1
            ],
            1,
            None,  # This is how the DERControlManager handles an aggregator level query
        ),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_filters(
    pg_base_config, expected_id_and_starts: list[tuple[int, datetime]], agg_id: int, site_id: int
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_base_config) as session:
        does = await select_does(session, agg_id, site_id, 0, datetime.min, 99)
        count = await count_does(session, agg_id, site_id, datetime.min)
        assert isinstance(count, int)
        assert len(does) == len(expected_id_and_starts)
        assert len(does) == count
        for (id, expected_datetime), doe in zip(expected_id_and_starts, does):
            assert_doe_for_id(id, site_id, expected_datetime, "Australia/Brisbane", doe)


@pytest.mark.parametrize(
    "expected_id_and_starts, agg_id, site_id",
    [
        (
            [(1, datetime(2022, 5, 6, 8, 2)), (2, datetime(2022, 5, 6, 10, 4)), (4, datetime(2022, 5, 7, 8, 2))],
            1,
            1,
        ),  # Adjusted for LA time
        ([(3, datetime(2022, 5, 6, 8, 2))], 1, 2),  # Adjusted for LA time
        ([], 2, 1),  # Adjusted for LA time
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_filters_la_time(
    pg_la_timezone, expected_id_and_starts: list[tuple[int, datetime]], agg_id: int, site_id: int
):
    """Builds on test_select_and_count_doe_filters with the la timezone"""
    async with generate_async_session(pg_la_timezone) as session:
        does = await select_does(session, agg_id, site_id, 0, datetime.min, 99)
        count = await count_does(session, agg_id, site_id, datetime.min)
        assert isinstance(count, int)
        assert len(does) == len(expected_id_and_starts)
        assert len(does) == count
        for (id, expected_datetime), doe in zip(expected_id_and_starts, does):
            assert_doe_for_id(id, site_id, expected_datetime, "America/Los_Angeles", doe)


@pytest.mark.parametrize(
    "expected_ids, start, after, limit",
    [
        ([1, 2], 0, datetime.min, 99),
        ([1], 0, datetime.min, 1),
        ([2], 1, datetime.min, 99),
        ([2], 1, datetime.min, 1),
        ([], 2, datetime.min, 99),
        ([], 0, datetime.min, 0),
        ([2], 0, datetime(2022, 5, 6, 12, 22, 32, tzinfo=timezone.utc), 99),
        ([], 0, datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc), 99),
    ],
)
@pytest.mark.anyio
async def test_select_doe_for_day_pagination(
    pg_base_config, expected_ids: list[int], start: int, after: datetime, limit: int
):
    """Tests out the basic pagination behavior"""
    async with generate_async_session(pg_base_config) as session:
        rates = await select_does_for_day(session, 1, 1, date(2022, 5, 7), start, after, limit)
        assert len(rates) == len(expected_ids)
        for id, rate in zip(expected_ids, rates):
            assert_doe_for_id(id, 1, None, None, rate)


@pytest.mark.parametrize(
    "expected_id_and_starts, agg_id, site_id, day",
    [
        ([(1, datetime(2022, 5, 7, 1, 2)), (2, datetime(2022, 5, 7, 3, 4))], 1, 1, date(2022, 5, 7)),
        ([(3, datetime(2022, 5, 7, 1, 2))], 1, 2, date(2022, 5, 7)),
        ([], 2, 1, date(2022, 5, 7)),
        ([], 1, 3, date(2022, 5, 7)),
        ([], 1, 1, date(2023, 5, 7)),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_for_day_filters(
    pg_base_config, expected_id_and_starts: list[tuple[int, datetime]], agg_id: int, site_id: int, day: date
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_base_config) as session:
        does = await select_does_for_day(session, agg_id, site_id, day, 0, datetime.min, 99)
        count = await count_does_for_day(session, agg_id, site_id, day, datetime.min)
        assert isinstance(count, int)
        assert len(does) == len(expected_id_and_starts)
        assert len(does) == count
        for (id, expected_datetime), doe in zip(expected_id_and_starts, does):
            assert_doe_for_id(id, site_id, expected_datetime, "Australia/Brisbane", doe)


@pytest.mark.parametrize(
    "expected_id_and_starts, agg_id, site_id, day",
    [
        (
            [(1, datetime(2022, 5, 6, 8, 2)), (2, datetime(2022, 5, 6, 10, 4))],
            1,
            1,
            date(2022, 5, 6),
        ),  # Adjusted for LA time
        ([(4, datetime(2022, 5, 7, 8, 2))], 1, 1, date(2022, 5, 7)),  # Adjusted for LA time
        ([], 1, 1, date(2022, 5, 8)),  # Adjusted for LA time
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_for_day_filters_la_time(
    pg_la_timezone, expected_id_and_starts: list[tuple[int, datetime]], agg_id: int, site_id: int, day: date
):
    """Builds on test_select_and_count_doe_for_day_filters with the la timezone"""
    async with generate_async_session(pg_la_timezone) as session:
        does = await select_does_for_day(session, agg_id, site_id, day, 0, datetime.min, 99)
        count = await count_does_for_day(session, agg_id, site_id, day, datetime.min)
        assert isinstance(count, int)
        assert len(does) == len(expected_id_and_starts)
        assert len(does) == count
        for (id, expected_datetime), doe in zip(expected_id_and_starts, does):
            assert_doe_for_id(id, site_id, expected_datetime, "America/Los_Angeles", doe)


@pytest.mark.parametrize(
    "expected_id_and_starts, timestamp, agg_id, site_id",
    [
        (
            [(5, datetime(2023, 5, 7, 1, 0, 0))],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
        ),
        (
            [(5, datetime(2023, 5, 7, 1, 0, 0)), (9, datetime(2023, 5, 7, 1, 0, 1))],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
        ),
        (
            [(5, datetime(2023, 5, 7, 1, 0, 0)), (9, datetime(2023, 5, 7, 1, 0, 1))],
            datetime(2023, 5, 7, 1, 3, 22, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
        ),
        (
            [(9, datetime(2023, 5, 7, 1, 0, 1)), (6, datetime(2023, 5, 7, 1, 5, 0))],
            datetime(2023, 5, 7, 1, 5, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
        ),
        (
            [(7, datetime(2023, 5, 7, 1, 10, 0))],
            datetime(2023, 5, 7, 1, 10, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
        ),
        # Throw the timestamp timezone off
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")), 1, 1),
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")), 1, 2),
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")), 2, 1),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_for_timestamp_filters(
    pg_additional_does,
    expected_id_and_starts: list[tuple[int, datetime]],
    timestamp: datetime,
    agg_id: int,
    site_id: int,
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_additional_does) as session:
        does = await select_does_at_timestamp(session, agg_id, site_id, timestamp, 0, datetime.min, 99)
        count = await count_does_at_timestamp(session, agg_id, site_id, timestamp, datetime.min)
        assert isinstance(count, int)
        assert len(does) == len(expected_id_and_starts)
        assert len(does) == count
        for (id, expected_datetime), doe in zip(expected_id_and_starts, does):
            assert_doe_for_id(id, site_id, expected_datetime, "Australia/Brisbane", doe, check_duration_seconds=False)


@pytest.mark.parametrize(
    "expected_ids, timestamp, start, after, limit",
    [
        # Start
        ([5, 9], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 0, datetime.min, 99),
        ([9], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 1, datetime.min, 99),
        ([], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 2, datetime.min, 99),
        # Limit
        ([5], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 0, datetime.min, 1),
        ([], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 0, datetime.min, 0),
        # After
        (
            [5, 9],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            0,
            datetime(2023, 2, 3, 11, 22, 32, tzinfo=timezone.utc),
            99,
        ),
        (
            [5],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            0,
            datetime(2023, 2, 3, 11, 22, 34, tzinfo=timezone.utc),
            99,
        ),
        (
            [],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            0,
            datetime(2023, 5, 6, 11, 22, 34, tzinfo=timezone.utc),
            99,
        ),
    ],
)
@pytest.mark.anyio
async def test_select_doe_at_timestamp_pagination(
    pg_additional_does, expected_ids: list[int], timestamp: datetime, start: int, after: datetime, limit: int
):
    """Tests out the basic pagination features for a timestamp that has 2 overlapping DOEs"""
    async with generate_async_session(pg_additional_does) as session:
        rates = await select_does_at_timestamp(session, 1, 1, timestamp, start, after, limit)
        assert len(rates) == len(expected_ids)
        for id, rate in zip(expected_ids, rates):
            assert_doe_for_id(id, 1, None, None, rate, check_duration_seconds=False)
