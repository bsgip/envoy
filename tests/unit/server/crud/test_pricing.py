from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_datetime_equal
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session

from envoy.server.crud.pricing import (
    count_tariff_rates_for_day,
    count_unique_rate_days,
    select_all_tariffs,
    select_rate_stats,
    select_single_tariff,
    select_tariff_count,
    select_tariff_generated_rate_for_scope,
    select_tariff_rate_for_day_time,
    select_tariff_rates_for_day,
    select_unique_rate_days,
)
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


@pytest.mark.anyio
async def test_select_tariff_count(pg_base_config):
    """Simple tests to ensure the counts work"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        assert await select_tariff_count(session, datetime.min) == 3

        # try with after filter being set
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 2, tzinfo=timezone.utc)) == 3
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 3, tzinfo=timezone.utc)) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 2, tzinfo=timezone.utc)) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 3, tzinfo=timezone.utc)) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 2, tzinfo=timezone.utc)) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 3, tzinfo=timezone.utc)) == 0


def assert_tariff_by_id(expected_tariff_id: Optional[int], actual_tariff: Optional[Tariff]):
    """Asserts tariff matches all values expected from a tariff with that id"""
    expected_currency_by_tariff_id = {
        1: 36,
        2: 124,
        3: 840,
    }
    if expected_tariff_id is None:
        assert actual_tariff is None
    else:
        assert actual_tariff
        assert actual_tariff.tariff_id == expected_tariff_id
        assert actual_tariff.currency_code == expected_currency_by_tariff_id[expected_tariff_id]
        assert actual_tariff.dnsp_code == f"tariff-dnsp-code-{expected_tariff_id}"
        assert actual_tariff.name == f"tariff-{expected_tariff_id}"


@pytest.mark.parametrize(
    "expected_ids, start, after, limit",
    [
        ([3, 2, 1], 0, datetime.min, 99),
        ([2, 1], 1, datetime.min, 99),
        ([1], 2, datetime.min, 99),
        ([], 99, datetime.min, 99),
        ([3, 2], 0, datetime.min, 2),
        ([1], 2, datetime.min, 2),
        ([], 3, datetime.min, 2),
        ([3, 2], 0, datetime(2023, 1, 2, 12, 1, 2, tzinfo=timezone.utc), 99),
        ([2], 1, datetime(2023, 1, 2, 12, 1, 2, tzinfo=timezone.utc), 99),
    ],
)
@pytest.mark.anyio
async def test_select_all_tariffs(pg_base_config, expected_ids: list[int], start: int, after: datetime, limit: int):
    """Tests that the returned tariffs match what's in the DB"""
    async with generate_async_session(pg_base_config) as session:
        tariffs = await select_all_tariffs(session, start, after, limit)
        assert len(tariffs) == len(expected_ids)
        assert [t.tariff_id for t in tariffs] == expected_ids

        # check contents of each entry
        for id, tariff in zip(expected_ids, tariffs):
            assert_tariff_by_id(id, tariff)


@pytest.mark.parametrize(
    "expected_id, requested_id",
    [
        (1, 1),
        (2, 2),
        (3, 3),
        (None, 4),
        (None, 999),
        (None, -1),
    ],
)
@pytest.mark.anyio
async def test_select_single_tariff(pg_base_config, expected_id: Optional[int], requested_id: int):
    """Tests that singular tariffs can be returned by id"""
    async with generate_async_session(pg_base_config) as session:
        tariff = await select_single_tariff(session, requested_id)
        assert_tariff_by_id(expected_id, tariff)


def assert_rate_for_id(
    expected_rate_id: Optional[int],
    expected_tariff_id: int,
    expected_site_id: int,
    expected_date: Optional[date],
    expected_time: Optional[time],
    expected_tz: Optional[str],
    actual_rate: Optional[TariffGeneratedRate],
):
    """Asserts the supplied rate matches the expected values for a rate with that id"""
    if expected_rate_id is None:
        assert actual_rate is None
    else:
        assert actual_rate
        assert actual_rate.tariff_generated_rate_id == expected_rate_id
        assert actual_rate.tariff_id == expected_tariff_id
        assert actual_rate.site_id == expected_site_id
        assert actual_rate.duration_seconds == 10 + expected_rate_id
        assert actual_rate.import_active_price == Decimal(f"{expected_rate_id}.1")
        assert actual_rate.export_active_price == Decimal(f"-{expected_rate_id}.22")
        assert actual_rate.import_reactive_price == Decimal(f"{expected_rate_id}.333")
        assert actual_rate.export_reactive_price == Decimal(f"-{expected_rate_id}.4444")
        if expected_date is not None and expected_time is not None:
            tz = ZoneInfo(expected_tz)
            assert_datetime_equal(actual_rate.start_time, datetime.combine(expected_date, expected_time, tzinfo=tz))
            assert actual_rate.start_time.tzname() == tz.tzname(
                actual_rate.start_time
            ), "Start time should be returned in local time"


@pytest.mark.parametrize(
    "expected_rate_id, agg_id, tariff_id, site_id, d, t",
    # expected_id, agg_id, tariff_id, site_id
    [
        (1, 1, 1, 1, date(2022, 3, 5), time(1, 2)),
        (2, 1, 1, 1, date(2022, 3, 5), time(3, 4)),
        (3, 1, 1, 2, date(2022, 3, 5), time(1, 2)),
        (4, 1, 1, 1, date(2022, 3, 6), time(1, 2)),
        (None, 2, 1, 1, date(2022, 3, 5), time(1, 2)),  # Wrong Aggregator
        (None, 1, 2, 1, date(2022, 3, 5), time(1, 2)),  # Wrong tariff
        (None, 1, 1, 4, date(2022, 3, 5), time(1, 2)),  # Wrong site
        (None, 1, 1, 1, date(2022, 3, 4), time(1, 2)),  # Wrong date
        (None, 1, 1, 1, date(2022, 3, 5), time(1, 1)),  # Wrong time
    ],
)
@pytest.mark.anyio
async def test_select_tariff_rate_for_day_time(
    pg_base_config, expected_rate_id: Optional[int], agg_id: int, tariff_id: int, site_id: int, d: date, t: time
):
    """Tests that fetching specific rates returns fully formed instances and respects all filter conditions"""
    async with generate_async_session(pg_base_config) as session:
        rate = await select_tariff_rate_for_day_time(session, agg_id, tariff_id, site_id, d, t)
        assert_rate_for_id(expected_rate_id, tariff_id, site_id, d, t, "Australia/Brisbane", rate)


@pytest.mark.parametrize(
    "expected_rate_id, agg_id, tariff_id, site_id, d, t",
    # expected_id, agg_id, tariff_id, site_id
    [
        (1, 1, 1, 1, date(2022, 3, 4), time(7, 2)),  # Adjusted LA Time
        (2, 1, 1, 1, date(2022, 3, 4), time(9, 4)),  # Adjusted LA Time
    ],
)
@pytest.mark.anyio
async def test_select_tariff_rate_for_day_time_la_time(
    pg_la_timezone, expected_rate_id: Optional[int], agg_id: int, tariff_id: int, site_id: int, d: date, t: time
):
    """Expands on test_select_tariff_rate_for_day_time by changing the site local time to LA time"""
    async with generate_async_session(pg_la_timezone) as session:
        rate = await select_tariff_rate_for_day_time(session, agg_id, tariff_id, site_id, d, t)
        assert_rate_for_id(expected_rate_id, tariff_id, site_id, d, t, "America/Los_Angeles", rate)


@pytest.mark.parametrize(
    "expected_ids, start, after, limit",
    [
        ([1, 2], 0, datetime.min, 99),
        ([1], 0, datetime.min, 1),
        ([2], 1, datetime.min, 99),
        ([2], 1, datetime.min, 1),
        ([], 2, datetime.min, 99),
        ([], 0, datetime.min, 0),
        ([2], 0, datetime(2022, 3, 4, 12, 22, 32, tzinfo=timezone.utc), 99),
        ([], 0, datetime(2022, 3, 4, 12, 22, 34, tzinfo=timezone.utc), 99),
    ],
)
@pytest.mark.anyio
async def test_select_tariff_rates_for_day_pagination(
    pg_base_config, expected_ids: list[int], start: int, after: datetime, limit: int
):
    """Tests out the basic pagination features"""
    async with generate_async_session(pg_base_config) as session:
        rates = await select_tariff_rates_for_day(session, 1, 1, 1, date(2022, 3, 5), start, after, limit)
    assert len(rates) == len(expected_ids)
    for id, rate in zip(expected_ids, rates):
        assert_rate_for_id(id, 1, 1, None, None, None, rate)


@pytest.mark.parametrize(
    "expected_id_and_starts, agg_id, tariff_id, site_id, day",
    [
        ([(1, datetime(2022, 3, 5, 1, 2)), (2, datetime(2022, 3, 5, 3, 4))], 1, 1, 1, date(2022, 3, 5)),
        ([], 2, 1, 1, date(2022, 3, 5)),
        ([], 1, 3, 1, date(2022, 3, 5)),
        ([], 1, 1, 4, date(2022, 3, 5)),
        ([], 1, 1, 1, date(2023, 3, 5)),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_tariff_rates_for_day_filters(
    pg_base_config,
    expected_id_and_starts: list[tuple[int, datetime]],
    agg_id: int,
    tariff_id: int,
    site_id: int,
    day: date,
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_base_config) as session:
        rates = await select_tariff_rates_for_day(session, agg_id, tariff_id, site_id, day, 0, datetime.min, 99)
        count = await count_tariff_rates_for_day(session, agg_id, tariff_id, site_id, day, datetime.min)
    assert isinstance(count, int)
    assert len(rates) == len(expected_id_and_starts)
    assert len(rates) == count
    for (id, expected_datetime), rate in zip(expected_id_and_starts, rates):
        assert_rate_for_id(
            id, tariff_id, site_id, expected_datetime.date(), expected_datetime.time(), "Australia/Brisbane", rate
        )


@pytest.mark.parametrize(
    "expected_id_and_starts, agg_id, tariff_id, site_id, day",
    [
        (
            [(1, datetime(2022, 3, 4, 7, 2)), (2, datetime(2022, 3, 4, 9, 4))],
            1,
            1,
            1,
            date(2022, 3, 4),
        ),  # Adjusted for LA time
        ([(4, datetime(2022, 3, 5, 7, 2))], 1, 1, 1, date(2022, 3, 5)),  # Adjusted for LA time
        ([], 1, 1, 1, date(2022, 3, 6)),  # Adjusted for LA time
    ],
)
@pytest.mark.anyio
async def test_select_and_count_tariff_rates_for_day_filters_la_time(
    pg_la_timezone,
    expected_id_and_starts: list[tuple[int, datetime]],
    agg_id: int,
    tariff_id: int,
    site_id: int,
    day: date,
):
    """Builds on test_select_and_count_tariff_rates_for_day_filters with the la timezone"""
    async with generate_async_session(pg_la_timezone) as session:
        rates = await select_tariff_rates_for_day(session, agg_id, tariff_id, site_id, day, 0, datetime.min, 99)
        count = await count_tariff_rates_for_day(session, agg_id, tariff_id, site_id, day, datetime.min)
        assert isinstance(count, int)
        assert len(rates) == len(expected_id_and_starts)
        assert len(rates) == count
        for (id, expected_datetime), rate in zip(expected_id_and_starts, rates):
            assert_rate_for_id(
                id, tariff_id, site_id, expected_datetime.date(), expected_datetime.time(), "America/Los_Angeles", rate
            )


@pytest.mark.parametrize(
    "filter, expected",
    [
        ((1, 1, 1, datetime.min), (3, datetime(2022, 3, 5, 1, 2), datetime(2022, 3, 6, 1, 2))),
        (
            (1, 1, 1, datetime(2022, 3, 4, 12, 22, 32, tzinfo=timezone.utc)),
            (2, datetime(2022, 3, 5, 3, 4), datetime(2022, 3, 6, 1, 2)),
        ),
        (
            (1, 1, 1, datetime(2022, 3, 4, 14, 22, 32, tzinfo=timezone.utc)),
            (1, datetime(2022, 3, 6, 1, 2), datetime(2022, 3, 6, 1, 2)),
        ),
        (
            (1, 1, 1, datetime(2022, 3, 4, 14, 22, 34, tzinfo=timezone.utc)),
            (0, None, None),
        ),  # filter miss on changed_after
        ((3, 1, 1, datetime.min), (0, None, None)),  # filter miss on agg_id
        ((1, 3, 1, datetime.min), (0, None, None)),  # filter miss on tariff_id
        ((1, 1, 4, datetime.min), (0, None, None)),  # filter miss on site_id
    ],
)
@pytest.mark.anyio
async def test_select_rate_stats(
    pg_base_config, filter: tuple[int, int, int, datetime], expected: tuple[int, datetime, datetime]
):
    """Tests the various filter options on select_rate_stats"""
    (agg_id, tariff_id, site_id, after) = filter
    (expected_count, expected_first, expected_last) = expected
    async with generate_async_session(pg_base_config) as session:
        stats = await select_rate_stats(session, agg_id, tariff_id, site_id, after)
        assert stats
        assert stats.total_rates == expected_count
        assert_datetime_equal(stats.first_rate, expected_first)
        assert_datetime_equal(stats.last_rate, expected_last)
        if stats.first_rate:
            assert stats.first_rate.tzname() == ZoneInfo("Australia/Brisbane").tzname(
                stats.first_rate
            ), "Expected datetime in local time"
        if stats.last_rate:
            assert stats.last_rate.tzname() == ZoneInfo("Australia/Brisbane").tzname(
                stats.last_rate
            ), "Expected datetime in local time"


@pytest.mark.parametrize(
    "filter, expected",
    [
        ((1, 1, 1, datetime.min), (3, datetime(2022, 3, 4, 7, 2), datetime(2022, 3, 5, 7, 2))),  # Adjusted to LA time
    ],
)
@pytest.mark.anyio
async def test_select_rate_stats_la_time(
    pg_la_timezone, filter: tuple[int, int, int, datetime], expected: tuple[int, datetime, datetime]
):
    """Tests the various filter options on select_rate_stats"""
    (agg_id, tariff_id, site_id, after) = filter
    (expected_count, expected_first, expected_last) = expected
    async with generate_async_session(pg_la_timezone) as session:
        stats = await select_rate_stats(session, agg_id, tariff_id, site_id, after)
        assert stats
        assert stats.total_rates == expected_count
        assert_datetime_equal(stats.first_rate, expected_first)
        assert_datetime_equal(stats.last_rate, expected_last)
        if stats.first_rate:
            assert stats.first_rate.tzname() == ZoneInfo("America/Los_Angeles").tzname(
                stats.first_rate
            ), "Expected datetime in local time"
        if stats.last_rate:
            assert stats.last_rate.tzname() == ZoneInfo("America/Los_Angeles").tzname(
                stats.last_rate
            ), "Expected datetime in local time"


@pytest.mark.parametrize(
    "agg_id, tariff_id, site_id, after, output_list",
    [
        (1, 1, 1, datetime.min, [date(2022, 3, 5), date(2022, 3, 6)]),
        (
            1,
            1,
            1,
            datetime(2022, 3, 4, 12, 22, 32, tzinfo=timezone.utc),
            [date(2022, 3, 5), date(2022, 3, 6)],
        ),
        (1, 1, 1, datetime(2022, 3, 4, 14, 22, 32, tzinfo=timezone.utc), [date(2022, 3, 6)]),
        (1, 1, 1, datetime(2022, 3, 4, 14, 22, 34, tzinfo=timezone.utc), []),  # filter miss on changed_after
        (3, 1, 1, datetime.min, []),  # filter miss on agg_id
        (1, 3, 1, datetime.min, []),  # filter miss on tariff_id
        (1, 1, 4, datetime.min, []),  # filter miss on site_id
    ],
)
@pytest.mark.anyio
async def test_select_unique_rate_days_filtering(
    pg_base_config, agg_id: int, tariff_id: int, site_id: int, after: datetime, output_list: list[tuple[date, int]]
):
    """Tests the various filter options on select_unique_rate_days and count_unique_rate_days"""
    async with generate_async_session(pg_base_config) as session:
        (unique_rate_days, select_count) = await select_unique_rate_days(
            session, agg_id, tariff_id, site_id, 0, after, 99
        )
        unique_rate_days_count = await count_unique_rate_days(session, agg_id, tariff_id, site_id, after)
        assert unique_rate_days_count == len(
            unique_rate_days
        ), "Without pagination limits the total count will equal the page count"
        assert select_count == unique_rate_days_count, "These should always align"
        assert unique_rate_days == output_list
        assert_list_type(date, unique_rate_days)


@pytest.mark.parametrize(
    "agg_id, tariff_id, site_id, after, output_list",
    [
        (1, 1, 1, datetime.min, [date(2022, 3, 4), date(2022, 3, 5)]),  # Adjusted LA time
    ],
)
@pytest.mark.anyio
async def test_select_unique_rate_days_filtering_la_time(
    pg_la_timezone, agg_id: int, tariff_id: int, site_id: int, after: datetime, output_list: list[tuple[date, int]]
):
    """Extends test_select_unique_rate_days_filtering with a test on different site timezones"""
    async with generate_async_session(pg_la_timezone) as session:
        (unique_rate_days, select_count) = await select_unique_rate_days(
            session, agg_id, tariff_id, site_id, 0, after, 99
        )
        unique_rate_days_count = await count_unique_rate_days(session, agg_id, tariff_id, site_id, after)
        assert unique_rate_days_count == len(
            unique_rate_days
        ), "Without pagination limits the total count will equal the page count"
        assert select_count == unique_rate_days_count, "These should always align"
        assert unique_rate_days == output_list
        assert_list_type(date, unique_rate_days)


@pytest.mark.parametrize(
    "start, limit, output_list",
    [
        (0, 99, [date(2022, 3, 5), date(2022, 3, 6)]),
        (1, 99, [date(2022, 3, 6)]),
        (2, 99, []),
        (0, 0, []),
        (0, 1, [date(2022, 3, 5)]),
        (1, 1, [date(2022, 3, 6)]),
        (2, 1, []),
    ],
)
@pytest.mark.anyio
async def test_select_unique_rate_days_pagination(
    pg_base_config, start: int, limit: int, output_list: list[tuple[date, int]]
):
    """Tests the various pagination options on select_unique_rate_days"""
    async with generate_async_session(pg_base_config) as session:
        (unique_rate_days, select_count) = await select_unique_rate_days(session, 1, 1, 1, start, datetime.min, limit)
        assert unique_rate_days == output_list
        assert isinstance(select_count, int)
        assert_list_type(date, unique_rate_days)


@pytest.mark.parametrize(
    "agg_id, site_id, rate_id, expected_site_id, expected_dt",
    [
        (1, 1, 1, 1, datetime(2022, 3, 5, 1, 2, 0)),
        (1, None, 1, 1, datetime(2022, 3, 5, 1, 2, 0)),  # Unscoped site
        (1, 1, 2, 1, datetime(2022, 3, 5, 3, 4, 0)),
        (1, None, 2, 1, datetime(2022, 3, 5, 3, 4, 0)),  # Unscoped site
        (1, 2, 3, 2, datetime(2022, 3, 5, 1, 2, 0)),
        (1, None, 3, 2, datetime(2022, 3, 5, 1, 2, 0)),  # Unscoped site
        (2, 1, 1, None, None),  # Bad Agg ID
        (99, 1, 1, None, None),  # Bad Agg ID
        (1, 2, 1, None, None),  # Bad Site ID
        (1, 99, 1, None, None),  # Bad Site ID
    ],
)
@pytest.mark.anyio
async def test_select_tariff_generated_rate_for_scope(
    pg_additional_does,
    agg_id: int,
    site_id: Optional[int],
    rate_id: int,
    expected_site_id: Optional[int],
    expected_dt: Optional[datetime],
):

    async with generate_async_session(pg_additional_does) as session:
        actual = await select_tariff_generated_rate_for_scope(session, agg_id, site_id, rate_id)
        if expected_site_id is None or expected_dt is None:
            expected_id = None
        else:
            expected_id = rate_id
        assert_rate_for_id(
            expected_rate_id=expected_id,
            expected_tariff_id=1,
            expected_site_id=expected_site_id,
            expected_date=None if expected_dt is None else expected_dt.date(),
            expected_time=None if expected_dt is None else expected_dt.time(),
            expected_tz="Australia/Brisbane",
            actual_rate=actual,
        )


@pytest.mark.parametrize(
    "agg_id, site_id, rate_id, expected_site_id, expected_dt",
    [
        (1, 1, 1, 1, datetime(2022, 3, 4, 7, 2, 0)),  # Adjusted for LA time
        (1, 1, 2, 1, datetime(2022, 3, 4, 9, 4, 0)),  # Adjusted for LA time
        (99, 99, 99, None, None),
    ],
)
@pytest.mark.anyio
async def test_select_tariff_generated_rate_for_scope_la_timezone(
    pg_la_timezone,
    agg_id: int,
    site_id: Optional[int],
    rate_id: int,
    expected_site_id: Optional[int],
    expected_dt: Optional[datetime],
):
    async with generate_async_session(pg_la_timezone) as session:
        actual = await select_tariff_generated_rate_for_scope(session, agg_id, site_id, rate_id)
        if expected_dt is None:
            expected_id = None
        else:
            expected_id = rate_id
        assert_rate_for_id(
            expected_rate_id=expected_id,
            expected_tariff_id=1,
            expected_site_id=expected_site_id,
            expected_date=None if expected_dt is None else expected_dt.date(),
            expected_time=None if expected_dt is None else expected_dt.time(),
            expected_tz="America/Los_Angeles",
            actual_rate=actual,
        )
