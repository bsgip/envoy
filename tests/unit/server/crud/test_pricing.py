from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

import pytest

from envoy.server.crud.pricing import (
    count_tariff_rates_for_day,
    select_all_tariffs,
    select_rate_daily_stats,
    select_rate_stats,
    select_single_tariff,
    select_tariff_count,
    select_tariff_rate_for_day_time,
    select_tariff_rates_for_day,
)
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from tests.assert_time import assert_datetime_equal
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_select_tariff_count(pg_base_config):
    """Simple tests to ensure the counts work"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        assert await select_tariff_count(session, datetime.min) == 3

        # try with after filter being set
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 2)) == 3
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 3)) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 2)) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 3)) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 2)) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 3)) == 0


def assert_tariff_by_id(expected_tariff_id: Optional[int], actual_tariff: Optional[Tariff]):
    """Asserts tariff matches all values expected from a tariff with that id"""

    if expected_tariff_id is None:
        assert actual_tariff is None
    else:
        assert actual_tariff
        assert actual_tariff.tariff_id == expected_tariff_id
        assert actual_tariff.currency_code == expected_tariff_id * 10 + expected_tariff_id
        assert actual_tariff.dnsp_code == f"tariff-dnsp-code-{expected_tariff_id}"
        assert actual_tariff.name == f"tariff-{expected_tariff_id}"


@pytest.mark.parametrize(
    "tariff_details",
    [([3, 2, 1], 0, datetime.min, 99),
     ([2, 1], 1, datetime.min, 99),
     ([1], 2, datetime.min, 99),
     ([], 99, datetime.min, 99),
     ([3, 2], 0, datetime.min, 2),
     ([1], 2, datetime.min, 2),
     ([], 3, datetime.min, 2),
     ([3, 2], 0, datetime(2023, 1, 2, 12, 1, 2), 99),
     ([2], 1, datetime(2023, 1, 2, 12, 1, 2), 99),
     ],
)
@pytest.mark.anyio
async def test_select_all_tariffs(pg_base_config, tariff_details: tuple[list[int], int, datetime, int]):
    """Tests that the returned tariffs match what's in the DB"""
    (expected_ids, start, after, limit) = tariff_details

    async with generate_async_session(pg_base_config) as session:
        tariffs = await select_all_tariffs(session, start, after, limit)
        assert len(tariffs) == len(expected_ids)
        assert [t.tariff_id for t in tariffs] == expected_ids

        # check contents of each entry
        for (id, tariff) in zip(expected_ids, tariffs):
            assert_tariff_by_id(id, tariff)


@pytest.mark.parametrize(
    "tariff_details",
    [(1, 1),
     (2, 2),
     (3, 3),
     (None, 4),
     (None, 999),
     (None, -1),
     ],
)
@pytest.mark.anyio
async def test_select_single_tariff(pg_base_config, tariff_details: tuple[Optional[int], int]):
    """Tests that singular tariffs can be returned by id"""
    (expected_id, requested_id) = tariff_details
    async with generate_async_session(pg_base_config) as session:
        tariff = await select_single_tariff(session, requested_id)
        assert_tariff_by_id(expected_id, tariff)


def assert_rate_for_id(expected_rate_id: Optional[int],
                       expected_tariff_id: int,
                       expected_site_id: int,
                       expected_date: Optional[date],
                       expected_time: Optional[time],
                       actual_rate: Optional[TariffGeneratedRate]):
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
            assert_datetime_equal(actual_rate.start_time, datetime.combine(expected_date, expected_time))


@pytest.mark.parametrize(
    "rate_details",
    # expected_id, agg_id, tariff_id, site_id
    [(1, 1, 1, 1, date(2022, 3, 5), time(1, 2)),
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
async def test_select_tariff_rate_for_day_time(pg_base_config, rate_details: tuple[Optional[int], int, int, int, date, time]):
    """Tests that fetching specific rates returns fully formed instances and respects all filter conditions"""
    (expected_rate_id, agg_id, tariff_id, site_id, d, t) = rate_details
    async with generate_async_session(pg_base_config) as session:
        rate = await select_tariff_rate_for_day_time(session, agg_id, tariff_id, site_id, d, t)
        assert_rate_for_id(expected_rate_id, tariff_id, site_id, d, t, rate)


@pytest.mark.parametrize(
    "page_details",
    [
        ([1, 2], 0, datetime.min, 99),
        ([1], 0, datetime.min, 1),
        ([2], 1, datetime.min, 99),
        ([2], 1, datetime.min, 1),
        ([], 2, datetime.min, 99),
        ([], 0, datetime.min, 0),
        ([2], 0, datetime(2022, 3, 4, 12, 22, 32), 99),
        ([], 0, datetime(2022, 3, 4, 12, 22, 34), 99),
     ],
)
@pytest.mark.anyio
async def test_select_tariff_rates_for_day_pagination(pg_base_config, page_details: tuple[list[int], int, datetime, int]):
    """Tests out the basic pagination features"""
    (expected_ids, start, after, limit) = page_details
    async with generate_async_session(pg_base_config) as session:
        rates = await select_tariff_rates_for_day(session, 1, 1, 1, date(2022, 3, 5), start, after, limit)
        assert len(rates) == len(expected_ids)
        for (id, rate) in zip(expected_ids, rates):
            assert_rate_for_id(id, 1, 1, None, None, rate)


@pytest.mark.parametrize(
    "filter_details",
    [
        ([1, 2], 1, 1, 1, date(2022, 3, 5)),

        ([], 2, 1, 1, date(2022, 3, 5)),
        ([], 1, 3, 1, date(2022, 3, 5)),
        ([], 1, 1, 4, date(2022, 3, 5)),
        ([], 1, 1, 1, date(2023, 3, 5)),
     ],
)
@pytest.mark.anyio
async def test_select_and_count_tariff_rates_for_day_filters(pg_base_config, filter_details: tuple[list[int], int, int, int, date]):
    """Tests out the basic filters features and validates the associated count function too"""
    (expected_ids, agg_id, tariff_id, site_id, day) = filter_details
    async with generate_async_session(pg_base_config) as session:
        rates = await select_tariff_rates_for_day(session, agg_id, tariff_id, site_id, day, 0, datetime.min, 99)
        count = await count_tariff_rates_for_day(session, agg_id, tariff_id, site_id, day, datetime.min)
        assert type(count) == int
        assert len(rates) == len(expected_ids)
        assert len(rates) == count
        for (id, rate) in zip(expected_ids, rates):
            assert_rate_for_id(id, tariff_id, site_id, None, None, rate)


@pytest.mark.parametrize(
    "expected_results",
    [
        ((1, 1, 1, datetime.min), (3, datetime(2022, 3, 5, 1, 2), datetime(2022, 3, 6, 1, 2))),
        ((1, 1, 1, datetime(2022, 3, 4, 12, 22, 32)), (2, datetime(2022, 3, 5, 3, 4), datetime(2022, 3, 6, 1, 2))),
        ((1, 1, 1, datetime(2022, 3, 4, 14, 22, 32)), (1, datetime(2022, 3, 6, 1, 2), datetime(2022, 3, 6, 1, 2))),
        ((1, 1, 1, datetime(2022, 3, 4, 14, 22, 34)), (0, None, None)),  # filter miss on changed_after
        ((3, 1, 1, datetime.min), (0, None, None)),  # filter miss on agg_id
        ((1, 3, 1, datetime.min), (0, None, None)),  # filter miss on tariff_id
        ((1, 1, 4, datetime.min), (0, None, None)),  # filter miss on site_id
     ],
)
@pytest.mark.anyio
async def test_select_rate_stats(pg_base_config, expected_results: tuple[tuple[int, int, int, datetime], tuple[int, datetime, datetime]]):
    """Tests the various filter options on select_rate_stats"""
    ((agg_id, tariff_id, site_id, after), (expected_count, expected_first, expected_last)) = expected_results
    async with generate_async_session(pg_base_config) as session:
        stats = await select_rate_stats(session, agg_id, tariff_id, site_id, after)
        assert stats
        assert stats.total_rates == expected_count
        assert_datetime_equal(stats.first_rate, expected_first)
        assert_datetime_equal(stats.last_rate, expected_last)


@pytest.mark.parametrize(
    "expected_results",
    [
        ((1, 1, 1, datetime.min), [(date(2022, 3, 5), 2), (date(2022, 3, 6), 1)]),
        ((1, 1, 1, datetime(2022, 3, 4, 12, 22, 32)), [(date(2022, 3, 5), 1), (date(2022, 3, 6), 1)]),
        ((1, 1, 1, datetime(2022, 3, 4, 14, 22, 32)), [(date(2022, 3, 6), 1)]),
        ((1, 1, 1, datetime(2022, 3, 4, 14, 22, 34)), []),  # filter miss on changed_after
        ((3, 1, 1, datetime.min), []),  # filter miss on agg_id
        ((1, 3, 1, datetime.min), []),  # filter miss on tariff_id
        ((1, 1, 4, datetime.min), []),  # filter miss on site_id
     ],
)
@pytest.mark.anyio
async def test_select_rate_daily_stats_filtering(pg_base_config, expected_results: tuple[tuple[int, int, int, datetime], list[tuple[date, int]]]):
    """Tests the various filter options on select_rate_daily_stats"""
    ((agg_id, tariff_id, site_id, after), output_list) = expected_results
    async with generate_async_session(pg_base_config) as session:
        daily_stats = await select_rate_daily_stats(session, agg_id, tariff_id, site_id, 0, after, 99)
        assert daily_stats.total_distinct_dates == len(daily_stats.single_date_counts), "Without pagination limits the total count will equal the page count"
        assert daily_stats.single_date_counts == output_list
        assert all([isinstance(d, date) for (d, _) in daily_stats.single_date_counts]), "Validating date type"
        assert all([isinstance(c, int) for (_, c) in daily_stats.single_date_counts]), "Validating int type"


@pytest.mark.parametrize(
    "expected_results",
    [
        ((0, 99), [(date(2022, 3, 5), 2), (date(2022, 3, 6), 1)]),
        ((1, 99), [(date(2022, 3, 6), 1)]),
        ((2, 99), []),
        ((0, 0), []),
        ((0, 1), [(date(2022, 3, 5), 2)]),
        ((1, 1), [(date(2022, 3, 6), 1)]),
        ((2, 1), []),
     ],
)
@pytest.mark.anyio
async def test_select_rate_daily_stats_pagination(pg_base_config, expected_results: tuple[tuple[int, int], list[tuple[date, int]]]):
    """Tests the various pagination options on select_rate_daily_stats"""
    ((start, limit), output_list) = expected_results
    expected_count = 2  # For agg/tariff/site = 1 (what we are testing here) - There are 2 distinct dates
    async with generate_async_session(pg_base_config) as session:
        daily_stats = await select_rate_daily_stats(session, 1, 1, 1, start, datetime.min, limit)
        assert daily_stats.single_date_counts == output_list
        assert daily_stats.total_distinct_dates == expected_count, "Date count is independent of pagination"
        assert all([isinstance(d, date) for (d, _) in daily_stats.single_date_counts]), "Validating date type"
        assert all([isinstance(c, int) for (_, c) in daily_stats.single_date_counts]), "Validating int type"
