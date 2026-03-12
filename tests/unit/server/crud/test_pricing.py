from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session

from envoy.server.crud.pricing import (
    count_active_rates_include_deleted,
    count_tariff_components_by_tariff,
    select_active_rates_include_deleted,
    select_all_tariffs,
    select_single_tariff,
    select_tariff_component_by_id,
    select_tariff_components_by_tariff,
    select_tariff_count,
    select_tariff_fsa_ids,
    select_tariff_generated_rate_include_deleted,
)
from envoy.server.crud.site import select_single_site_with_site_id
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate

AEST = timezone(timedelta(hours=10))
UTC = timezone.utc
BASE = datetime(2000, 1, 1, tzinfo=UTC)  # Convenience - used a lot for initial creation times


@pytest.mark.parametrize(
    "changed_after, expected_fsa_ids",
    [
        (datetime.min, [1, 2]),
        (datetime(2023, 1, 2, 12, 1, 0, tzinfo=UTC), [1, 2]),
        (datetime(2023, 1, 2, 12, 2, 0, tzinfo=UTC), [2]),
        (datetime(2023, 1, 2, 13, 2, 0, tzinfo=UTC), []),
    ],
)
@pytest.mark.anyio
async def test_select_tariff_fsa_ids(pg_base_config, changed_after: datetime, expected_fsa_ids: list[int]):
    async with generate_async_session(pg_base_config) as session:
        actual_ids = await select_tariff_fsa_ids(session, changed_after)
        assert_list_type(int, actual_ids, len(expected_fsa_ids))
        assert set(expected_fsa_ids) == set(actual_ids)


@pytest.mark.anyio
async def test_select_tariff_count(pg_base_config):
    """Simple tests to ensure the counts work"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        assert await select_tariff_count(session, datetime.min, None) == 3

        # Check fsa_id
        assert await select_tariff_count(session, datetime.min, 1) == 2
        assert await select_tariff_count(session, datetime.min, 2) == 1
        assert await select_tariff_count(session, datetime.min, 3) == 0

        # try with after filter being set
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 2, tzinfo=UTC), None) == 3
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 3, tzinfo=UTC), None) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 2, tzinfo=UTC), None) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 3, tzinfo=UTC), None) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 2, tzinfo=UTC), None) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 3, tzinfo=UTC), None) == 0

        # Combo after and fsa_id filter
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 3, tzinfo=UTC), 1) == 0
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 3, tzinfo=UTC), 2) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 3, tzinfo=UTC), 3) == 0


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
    "expected_ids, start, after, limit, fsa_id",
    [
        ([3, 2, 1], 0, datetime.min, 99, None),
        ([2, 1], 0, datetime.min, 99, 1),
        ([3], 0, datetime.min, 99, 2),
        ([], 0, datetime.min, 99, 3),
        ([2, 1], 1, datetime.min, 99, None),
        ([1], 2, datetime.min, 99, None),
        ([], 99, datetime.min, 99, None),
        ([3, 2], 0, datetime.min, 2, None),
        ([1], 2, datetime.min, 2, None),
        ([], 3, datetime.min, 2, None),
        ([3, 2], 0, datetime(2023, 1, 2, 12, 1, 2, tzinfo=UTC), 99, None),
        ([2], 0, datetime(2023, 1, 2, 12, 1, 2, tzinfo=UTC), 99, 1),
        ([2], 1, datetime(2023, 1, 2, 12, 1, 2, tzinfo=UTC), 99, None),
    ],
)
@pytest.mark.anyio
async def test_select_all_tariffs(
    pg_base_config, expected_ids: list[int], start: int, after: datetime, limit: int, fsa_id: Optional[int]
):
    """Tests that the returned tariffs match what's in the DB"""
    async with generate_async_session(pg_base_config) as session:
        tariffs = await select_all_tariffs(session, start, after, limit, fsa_id)
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


def assert_tariff_component_for_id(
    expected_tariff_component_id: Optional[int],
    actual_tariff_component: Optional[TariffComponent],
):
    """Asserts the supplied tariff component matches the expected values for a rate with that id (defined in
    base_config.sql)"""
    if expected_tariff_component_id is None:
        assert actual_tariff_component is None
    else:
        assert isinstance(actual_tariff_component, TariffComponent)
        assert actual_tariff_component.tariff_component_id == expected_tariff_component_id
        match (expected_tariff_component_id):
            case 1:
                assert actual_tariff_component.role_flags == 1
                assert actual_tariff_component.accumulation_behaviour == 3
                assert actual_tariff_component.commodity == 2
                assert actual_tariff_component.flow_direction == 1
                assert actual_tariff_component.phase == 0
                assert actual_tariff_component.power_of_ten_multiplier == 3
                assert actual_tariff_component.uom == 38
            case 2:
                assert actual_tariff_component.role_flags == 1
                assert actual_tariff_component.accumulation_behaviour is None
                assert actual_tariff_component.commodity is None
                assert actual_tariff_component.flow_direction == 19
                assert actual_tariff_component.phase is None
                assert actual_tariff_component.power_of_ten_multiplier is None
                assert actual_tariff_component.uom == 38
            case 3:
                assert actual_tariff_component.accumulation_behaviour is None
                assert actual_tariff_component.role_flags == 3
                assert actual_tariff_component.commodity is None
                assert actual_tariff_component.flow_direction is None
                assert actual_tariff_component.power_of_ten_multiplier is None
                assert actual_tariff_component.uom is None
            case 4:
                assert actual_tariff_component.role_flags == 3
                assert actual_tariff_component.accumulation_behaviour == 3
                assert actual_tariff_component.commodity == 2
                assert actual_tariff_component.flow_direction == 1
                assert actual_tariff_component.phase == 0
                assert actual_tariff_component.power_of_ten_multiplier == 3
                assert actual_tariff_component.uom == 38
            case _:
                raise Exception(f"Unexpected {expected_tariff_component_id=}")

        assert actual_tariff_component.created_time == datetime(2000, 1, 1, tzinfo=UTC)
        assert actual_tariff_component.changed_time == datetime(
            2022, 2, 1, 0, tzinfo=timezone(timedelta(hours=10))
        ) + timedelta(hours=expected_tariff_component_id)


@pytest.mark.parametrize(
    "requested_id, expected_id",
    [
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (0, None),
        (999, None),
        (-1, None),
    ],
)
@pytest.mark.anyio
async def test_select_tariff_component_by_id(pg_base_config, requested_id: int, expected_id: Optional[int]):
    async with generate_async_session(pg_base_config) as session:
        tariff_component = await select_tariff_component_by_id(session, requested_id)
        assert_tariff_component_for_id(expected_id, tariff_component)


@pytest.mark.parametrize(
    "tariff_id, start, changed_after, limit, expected_ids, expected_count",
    [
        (1, 0, None, 99, [3, 2, 1], 3),
        (2, 0, None, 99, [4], 1),
        (3, 0, None, 99, [], 0),
        (99, 0, None, 99, [], 0),
        (1, 0, datetime(2022, 2, 1, 1, 30, 0, tzinfo=timezone(timedelta(hours=10))), 99, [3, 2], 2),
        (1, 1, datetime(2022, 2, 1, 1, 30, 0, tzinfo=timezone(timedelta(hours=10))), 99, [2], 2),
        # Paging
        (1, 1, None, 99, [2, 1], 3),
        (1, 2, None, 99, [1], 3),
        (1, 99, None, 99, [], 3),
        (1, 1, None, 1, [2], 3),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_tariff_components_by_tariff(
    pg_base_config,
    tariff_id: int,
    start: int,
    changed_after: Optional[datetime],
    limit: int,
    expected_ids: list[int],
    expected_count: int,
):
    async with generate_async_session(pg_base_config) as session:
        count = await count_tariff_components_by_tariff(session, tariff_id, changed_after)
        assert isinstance(count, int)
        assert count == expected_count

        tariff_components = await select_tariff_components_by_tariff(session, tariff_id, start, changed_after, limit)
        assert_list_type(TariffComponent, tariff_components, count=len(expected_ids))
        for expected_id, tc in zip(expected_ids, tariff_components):
            assert_tariff_component_for_id(expected_id, tc)


def assert_rate_for_id(
    expected_rate_id: Optional[int],
    actual_rate: Optional[Union[TariffGeneratedRate, ArchiveTariffGeneratedRate, None]],
):
    """Asserts the supplied rate matches the expected values for a rate with that id - sourced from base_config.sql"""
    if expected_rate_id is None:
        assert actual_rate is None
    else:
        assert actual_rate is not None

        # This is purely a shorthand convention in the base_config.sql / additional_prices.sql data
        if expected_rate_id <= 7:
            assert isinstance(actual_rate, TariffGeneratedRate)
        else:
            assert isinstance(actual_rate, ArchiveTariffGeneratedRate)

        # Some values can be inferred from the ID (simple pattern)
        assert actual_rate.tariff_generated_rate_id == expected_rate_id
        assert actual_rate.duration_seconds == 11 * expected_rate_id
        assert actual_rate.end_time == actual_rate.start_time + timedelta(seconds=actual_rate.duration_seconds)
        assert actual_rate.price_pow10_encoded == 1111 * expected_rate_id

        # Other things are specific to the individual records
        match (expected_rate_id):
            case 1:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_id == 1
                assert actual_rate.calculation_log_id == 2
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 2:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_id == 1
                assert actual_rate.calculation_log_id == 2
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 11, tzinfo=AEST)
            case 3:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_id == 1
                assert actual_rate.calculation_log_id == 2
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 33, tzinfo=AEST)
            case 4:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_id == 2
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 5:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_id == 3
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 6:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 2
                assert actual_rate.site_id == 1
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 7:
                assert actual_rate.tariff_id == 2
                assert actual_rate.tariff_component_id == 4
                assert actual_rate.site_id == 1
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 8:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_id == 1
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 1, 6, tzinfo=AEST)
                assert actual_rate.deleted_time == datetime(2022, 3, 5, 1, 30, 0, tzinfo=UTC)
            case 9:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_id == 1
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 2, 34, tzinfo=AEST)
                assert actual_rate.deleted_time == datetime(2022, 3, 5, 1, 35, 0, tzinfo=UTC)
            case _:
                raise Exception(f"Unexpected {expected_rate_id=}")


@pytest.mark.parametrize(
    "agg_id, site_id, rate_id, expected_rate_id",
    [
        (1, 1, 1, 1),
        (1, None, 1, 1),
        (1, 1, 3, 3),
        (1, None, 3, 3),
        (2, 3, 5, 5),
        (2, None, 5, 5),
        (1, 1, 8, 8),  # Archive
        (1, None, 8, 8),  # Archive
        (1, 1, 9, 9),  # Archive
        (1, None, 9, 9),  # Archive
        (1, 1, 99, None),  # Bad Rate ID
        (2, 1, 1, None),  # Bad Agg ID
        (99, 1, 1, None),  # Bad Agg ID
        (1, 2, 1, None),  # Bad Site ID
        (1, 99, 1, None),  # Bad Site ID
        (2, 1, 8, None),  # Bad Agg ID
        (99, 1, 8, None),  # Bad Agg ID
        (1, 2, 8, None),  # Bad Site ID
        (1, 99, 8, None),  # Bad Site ID
    ],
)
@pytest.mark.anyio
async def test_select_tariff_generated_rate_include_deleted(
    pg_additional_prices, agg_id: int, site_id: Optional[int], rate_id: int, expected_rate_id: Optional[int]
):

    async with generate_async_session(pg_additional_prices) as session:
        actual = await select_tariff_generated_rate_include_deleted(session, agg_id, site_id, rate_id)
        assert_rate_for_id(expected_rate_id=expected_rate_id, actual_rate=actual)


@pytest.mark.parametrize(
    "agg_id, site_id, rate_id",
    [
        (1, 1, 1),
        (1, None, 1),
        (1, 1, 8),
        (1, None, 8),
    ],
)
@pytest.mark.anyio
async def test_select_tariff_generated_rate_for_scope_la_timezone(
    pg_la_timezone, pg_additional_prices, agg_id: int, site_id: Optional[int], rate_id: int
):
    async with generate_async_session(pg_la_timezone) as session:
        actual = await select_tariff_generated_rate_include_deleted(session, agg_id, site_id, rate_id)
        assert_rate_for_id(expected_rate_id=rate_id, actual_rate=actual)
        if actual is not None:
            assert actual.start_time.tzinfo == ZoneInfo("America/Los_Angeles")


@pytest.mark.parametrize(
    "expected_ids, expected_count, tariff_id, tariff_component_id, site_id, now, start, changed_after, limit",
    [
        # Site #1 - ANY TC
        ([6, 1, 2, 3, 8, 9], 6, 1, None, 1, BASE, 0, datetime.min, 99),
        ([6, 1, 2, 3, 8, 9], 6, 1, None, 1, BASE, 0, None, 99),
        # Site #1 - TC #1
        ([1, 2, 3, 8, 9], 5, 1, 1, 1, BASE, 0, datetime.min, 99),
        # Site #1 - TC #2
        ([6], 1, 1, 2, 1, BASE, 0, datetime.min, 99),
        ([6], 1, 1, 2, 1, BASE, 0, None, 99),
        # Site #1 - TC #3
        ([], 0, 1, 3, 1, BASE, 0, datetime.min, 99),
        # Site #1 - TC #DNE
        ([], 0, 1, 99, 1, BASE, 0, datetime.min, 99),
        # Tariff #2 Site #1 - ANY TC
        ([7], 1, 2, None, 1, BASE, 0, datetime.min, 99),
        # Tariff #3 Site #1 - ANY TC
        ([], 0, 3, None, 1, BASE, 0, datetime.min, 99),
        # Tariff #DNE Site #1 - ANY TC
        ([], 0, 99, None, 1, BASE, 0, datetime.min, 99),
        # Adjusting "now" to exclude expired items (will exclude #1 / #2)
        ([6, 3, 8, 9], 4, 1, None, 1, datetime(2022, 3, 5, 1, 0, 35, tzinfo=AEST), 0, datetime.min, 99),
        # Adjusting "now" to exclude most items (will exclude everything but #9)
        ([9], 1, 1, None, 1, datetime(2022, 3, 5, 1, 2, 35, tzinfo=AEST), 0, datetime.min, 99),
        # Adjusting "now" to exclude all items
        ([], 0, 1, None, 1, datetime(2025, 1, 1, 1, 1, 1, tzinfo=AEST), 0, datetime.min, 99),
        # Adjusting changed time filter to exclude items (noting archives filter on deleted_time, not changed_time)
        ([6, 1, 2, 3, 8, 9], 6, 1, None, 1, BASE, 0, BASE, 99),
        ([6, 3, 8, 9], 4, 1, None, 1, BASE, 0, datetime(2022, 3, 4, 13, 22, 33, tzinfo=UTC), 99),
        ([9], 1, 1, None, 1, BASE, 0, datetime(2022, 3, 5, 1, 31, 0, tzinfo=UTC), 99),
        ([], 0, 1, None, 1, BASE, 0, datetime(2022, 3, 5, 20, 22, 33, tzinfo=UTC), 99),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_active_rates_include_deleted(
    pg_additional_prices,
    expected_ids: list[int],
    expected_count: int,
    tariff_id: int,
    tariff_component_id: Optional[int],
    site_id: int,
    now: datetime,
    start: int,
    changed_after: Optional[datetime],
    limit: int,
):
    """Tests that count_active_rates_include_deleted and select_active_rates_include_deleted both handle archives
    and pagination correctly."""

    async with generate_async_session(pg_additional_prices) as session:
        existing_site = await select_single_site_with_site_id(session, 1, site_id)
        assert existing_site is not None, "This is a test definition issue if failing"

        # Check the rates
        actual_rates = await select_active_rates_include_deleted(
            session,
            tariff_id=tariff_id,
            tariff_component_id=tariff_component_id,
            site=existing_site,
            now=now,
            start=start,
            changed_after=changed_after,
            limit=limit,
        )

        assert expected_ids == [r.tariff_generated_rate_id for r in actual_rates]
        for actual_rate, expected_id in zip(actual_rates, expected_ids):
            assert_rate_for_id(expected_rate_id=expected_id, actual_rate=actual_rate)
        assert len(actual_rates) == len(expected_ids)

        # Check the count
        actual_count = await count_active_rates_include_deleted(
            session,
            tariff_id=tariff_id,
            tariff_component_id=tariff_component_id,
            site_id=site_id,
            now=now,
            changed_after=changed_after,
        )
        assert isinstance(actual_count, int)
        assert actual_count == expected_count
