from datetime import UTC, datetime, timedelta, timezone

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
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
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate

AEST = timezone(timedelta(hours=10))
UTC = UTC
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


def assert_tariff_by_id(expected_tariff_id: int | None, actual_tariff: Tariff | None):
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
    pg_base_config, expected_ids: list[int], start: int, after: datetime, limit: int, fsa_id: int | None
):
    """Tests that the returned tariffs match what's in the DB"""
    async with generate_async_session(pg_base_config) as session:
        tariffs = await select_all_tariffs(session, start, after, limit, fsa_id)
        assert len(tariffs) == len(expected_ids)
        assert [t.tariff_id for t in tariffs] == expected_ids

        # check contents of each entry
        for id, tariff in zip(expected_ids, tariffs, strict=False):
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
async def test_select_single_tariff(pg_base_config, expected_id: int | None, requested_id: int):
    """Tests that singular tariffs can be returned by id"""
    async with generate_async_session(pg_base_config) as session:
        tariff = await select_single_tariff(session, requested_id)
        assert_tariff_by_id(expected_id, tariff)


def assert_tariff_component_for_id(
    expected_tariff_component_id: int | None,
    actual_tariff_component: TariffComponent | None,
):
    """Asserts the supplied tariff component matches the expected values for a rate with that id (defined in
    base_config.sql)"""
    if expected_tariff_component_id is None:
        assert actual_tariff_component is None
    else:
        assert isinstance(actual_tariff_component, TariffComponent)
        assert actual_tariff_component.tariff_component_id == expected_tariff_component_id
        match expected_tariff_component_id:
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
async def test_select_tariff_component_by_id(pg_base_config, requested_id: int, expected_id: int | None):
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
    changed_after: datetime | None,
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
        for expected_id, tc in zip(expected_ids, tariff_components, strict=False):
            assert_tariff_component_for_id(expected_id, tc)


def assert_rate_for_id(
    expected_rate_id: int | None,
    actual_rate: TariffGeneratedRate | ArchiveTariffGeneratedRate | None | None,
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

        if expected_rate_id in {2, 4}:
            assert actual_rate.block_1_start_pow10_encoded is None
            assert actual_rate.price_pow10_encoded_block_1 is None
        else:
            assert actual_rate.block_1_start_pow10_encoded == expected_rate_id * 1000
            assert actual_rate.price_pow10_encoded_block_1 == (expected_rate_id * 1000) + 1

        # Other things are specific to the individual records
        match expected_rate_id:
            case 1:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_group_id == 2
                assert actual_rate.calculation_log_id == 2
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 2:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_group_id == 2
                assert actual_rate.calculation_log_id == 2
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 11, tzinfo=AEST)
            case 3:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_group_id == 2
                assert actual_rate.calculation_log_id == 2
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 33, tzinfo=AEST)
            case 4:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_group_id == 4
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 5:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_group_id == 5
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 6:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 2
                assert actual_rate.site_group_id == 2
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 7:
                assert actual_rate.tariff_id == 2
                assert actual_rate.tariff_component_id == 4
                assert actual_rate.site_group_id == 2
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 0, 0, tzinfo=AEST)
            case 8:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_group_id == 2
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 1, 6, tzinfo=AEST)
                assert actual_rate.deleted_time == datetime(2022, 3, 5, 1, 30, 0, tzinfo=UTC)  # ty:ignore[missing-union-attribute]
            case 9:
                assert actual_rate.tariff_id == 1
                assert actual_rate.tariff_component_id == 1
                assert actual_rate.site_group_id == 2
                assert actual_rate.calculation_log_id is None
                assert actual_rate.start_time == datetime(2022, 3, 5, 1, 2, 34, tzinfo=AEST)
                assert actual_rate.deleted_time == datetime(2022, 3, 5, 1, 35, 0, tzinfo=UTC)  # ty:ignore[missing-union-attribute]
            case _:
                raise Exception(f"Unexpected {expected_rate_id=}")


@pytest.mark.parametrize(
    "agg_id, site_id, rate_id, expected_rate_id",
    [
        (1, 1, 1, 1),
        (1, 1, 3, 3),
        (2, 3, 5, 5),
        (1, 1, 8, 8),  # Archive
        (1, 1, 9, 9),  # Archive
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
    pg_additional_prices, agg_id: int, site_id: int, rate_id: int, expected_rate_id: int | None
):

    async with generate_async_session(pg_additional_prices) as session:
        actual = await select_tariff_generated_rate_include_deleted(session, agg_id, site_id, rate_id)
        assert_rate_for_id(expected_rate_id=expected_rate_id, actual_rate=actual)


@pytest.mark.parametrize(
    "expected_ids, expected_count, tariff_id, tariff_component_id, site_group_ids, now, start, changed_after, limit",
    [
        # No groups matched - return nothing
        ([], 0, 1, None, set(), BASE, 0, datetime.min, 99),
        # All groups - ANY TC
        ([6, 5, 4, 1, 2, 3, 8, 9], 8, 1, None, {1, 2, 3, 4, 5, 99}, BASE, 0, datetime.min, 99),
        ([7], 1, 2, None, {1, 2, 3, 4, 5, 99}, BASE, 0, datetime.min, 99),
        # Site #1 - ANY TC
        ([6, 1, 2, 3, 8, 9], 6, 1, None, {1, 2}, BASE, 0, datetime.min, 99),
        ([6, 1, 2, 3, 8, 9], 6, 1, None, {1, 2}, BASE, 0, None, 99),
        # Site #1 - TC #1
        ([1, 2, 3, 8, 9], 5, 1, 1, {1, 2}, BASE, 0, datetime.min, 99),
        # Site #1 - TC #2
        ([6], 1, 1, 2, {1, 2}, BASE, 0, datetime.min, 99),
        ([6], 1, 1, 2, {1, 2}, BASE, 0, None, 99),
        # Site #1 - TC #3
        ([], 0, 1, 3, {1, 2}, BASE, 0, datetime.min, 99),
        # Site #1 - TC #DNE
        ([], 0, 1, 99, {1, 2}, BASE, 0, datetime.min, 99),
        # Tariff #2 Site #1 - ANY TC
        ([7], 1, 2, None, {1, 2}, BASE, 0, datetime.min, 99),
        # Tariff #3 Site #1 - ANY TC
        ([], 0, 3, None, {1, 2}, BASE, 0, datetime.min, 99),
        # Tariff #DNE Site #1 - ANY TC
        ([], 0, 99, None, {1, 2}, BASE, 0, datetime.min, 99),
        # Adjusting "now" to exclude expired items (will exclude #1 / #2)
        ([6, 3, 8, 9], 4, 1, None, {1, 2}, datetime(2022, 3, 5, 1, 0, 35, tzinfo=AEST), 0, datetime.min, 99),
        # Adjusting "now" to exclude most items (will exclude everything but #9)
        ([9], 1, 1, None, {1, 2}, datetime(2022, 3, 5, 1, 2, 35, tzinfo=AEST), 0, datetime.min, 99),
        # Adjusting "now" to exclude all items
        ([], 0, 1, None, {1, 2}, datetime(2025, 1, 1, 1, 1, 1, tzinfo=AEST), 0, datetime.min, 99),
        # Adjusting changed time filter to exclude items (noting archives filter on deleted_time, not changed_time)
        ([6, 1, 2, 3, 8, 9], 6, 1, None, {1, 2}, BASE, 0, BASE, 99),
        ([6, 3, 8, 9], 4, 1, None, {1, 2}, BASE, 0, datetime(2022, 3, 4, 13, 22, 33, tzinfo=UTC), 99),
        ([9], 1, 1, None, {1, 2}, BASE, 0, datetime(2022, 3, 5, 1, 31, 0, tzinfo=UTC), 99),
        ([], 0, 1, None, {1, 2}, BASE, 0, datetime(2022, 3, 5, 20, 22, 33, tzinfo=UTC), 99),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_active_rates_include_deleted(
    pg_additional_prices,
    expected_ids: list[int],
    expected_count: int,
    tariff_id: int,
    tariff_component_id: int | None,
    site_group_ids: set[int],
    now: datetime,
    start: int,
    changed_after: datetime | None,
    limit: int,
):
    """Tests that count_active_rates_include_deleted and select_active_rates_include_deleted both handle archives
    and pagination correctly."""

    async with generate_async_session(pg_additional_prices) as session:
        # Check the rates
        actual_rates = await select_active_rates_include_deleted(
            session,
            tariff_id=tariff_id,
            tariff_component_id=tariff_component_id,
            site_group_ids=site_group_ids,
            now=now,
            start=start,
            changed_after=changed_after,
            limit=limit,
        )

        assert expected_ids == [r.tariff_generated_rate_id for r in actual_rates]
        for actual_rate, expected_id in zip(actual_rates, expected_ids, strict=False):
            assert_rate_for_id(expected_rate_id=expected_id, actual_rate=actual_rate)
        assert len(actual_rates) == len(expected_ids)

        # Check the count
        actual_count = await count_active_rates_include_deleted(
            session,
            tariff_id=tariff_id,
            tariff_component_id=tariff_component_id,
            site_group_ids=site_group_ids,
            now=now,
            changed_after=changed_after,
        )
        assert isinstance(actual_count, int)
        assert actual_count == expected_count


@pytest.fixture
async def tariff_with_required_site_group(pg_base_config):
    """Adds a Tariff (id 4) whose required_site_group_id is set to site2's singleton group (id 4) - only site2
    should be able to "see" this Tariff"""
    async with generate_async_session(pg_base_config) as session:
        session.add(
            generate_class_instance(
                Tariff,
                seed=404,
                tariff_id=4,
                fsa_id=None,
                required_site_group_id=4,
                changed_time=datetime(2023, 1, 2, 14, 1, 2, tzinfo=UTC),
            )
        )
        await session.commit()
    yield pg_base_config


@pytest.mark.parametrize(
    "site_group_ids, expected_visible",
    [
        (None, True),  # No site scope (eg admin) - always visible
        ({4}, True),
        ({1, 99, 4}, True),
        ({1, 2, 3, 99}, False),
        ({3}, False),
        (set(), False),
    ],
)
@pytest.mark.anyio
async def test_select_single_tariff_required_site_group_id_filtering(
    tariff_with_required_site_group, site_group_ids: set[int] | None, expected_visible: bool
):
    async with generate_async_session(tariff_with_required_site_group) as session:
        result = await select_single_tariff(session, 4, site_group_ids=site_group_ids)
        if expected_visible:
            assert result is not None
            assert result.tariff_id == 4
        else:
            assert result is None


@pytest.mark.parametrize(
    "site_group_ids, expect_included",
    [
        (None, True),
        ({1, 4}, True),
        ({4, 99}, True),
        ({1, 2}, False),
        ({1, 5}, False),
        (set(), False),
    ],
)
@pytest.mark.anyio
async def test_select_all_tariffs_and_count_required_site_group_id_filtering(
    tariff_with_required_site_group, site_group_ids: set[int] | None, expect_included: bool
):
    async with generate_async_session(tariff_with_required_site_group) as session:
        tariffs = await select_all_tariffs(session, 0, datetime.min, 99, None, site_group_ids=site_group_ids)
        tariff_ids = [t.tariff_id for t in tariffs]
        count = await select_tariff_count(session, datetime.min, None, site_group_ids=site_group_ids)

        if expect_included:
            assert 4 in tariff_ids
        else:
            assert 4 not in tariff_ids

        assert count == len(tariffs), "Count and list results should agree on visibility filtering"
