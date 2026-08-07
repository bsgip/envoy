from datetime import UTC, datetime, timedelta, timezone

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.asserts.type import assert_dict_type, assert_list_type
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from envoy.admin.crud.pricing import (
    cancel_and_delete_tariff_component,
    cancel_colliding_tariff_generated_rates,
    cancel_tariff_generated_rate,
    count_filtered_tariff_generated_rates,
    insert_many_tariff_genrate,
    insert_many_tariff_genrate_ignore_collisions,
    insert_single_tariff,
    select_filtered_tariff_generated_rates,
    select_single_tariff_generated_rate,
    select_tariff_ids_for_component_ids,
    update_single_tariff,
    update_single_tariff_component,
)
from envoy.server.crud.pricing import select_single_tariff, select_tariff_component_by_id
from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffComponent, ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate


async def _select_latest_tariff_generated_rate(session) -> TariffGeneratedRate:
    stmt = select(TariffGeneratedRate).order_by(TariffGeneratedRate.tariff_generated_rate_id.desc()).limit(1)
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def _select_tariff_generated_rate_by_id(session, id: int) -> TariffGeneratedRate | None:
    stmt = select(TariffGeneratedRate).where(TariffGeneratedRate.tariff_generated_rate_id == id)
    resp = await session.execute(stmt)
    return resp.scalar_one()


@pytest.mark.anyio
async def test_insert_single_tariff(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        tariff_in = generate_class_instance(Tariff, tariff_id=None, required_site_group_id=None)
        await insert_single_tariff(session, tariff_in)

        await session.flush()

        assert tariff_in.tariff_id == 1
        tariff = await select_single_tariff(session, tariff_in.tariff_id)
        assert tariff is not None

        assert_class_instance_equality(Tariff, tariff, tariff_in)
        assert tariff.created_time is not None
        assert_nowish(tariff.created_time)

        # No archival on insert
        assert (await session.execute(select(func.count()).select_from(ArchiveTariff))).scalar_one() == 0


@pytest.mark.anyio
async def test_update_single_tariff(pg_base_config):
    changed_time = datetime(2016, 6, 7, 14, 6, 8, tzinfo=UTC)
    async with generate_async_session(pg_base_config) as session:
        tariff_in = generate_class_instance(Tariff, required_site_group_id=None)
        tariff_in.tariff_id = 1
        await update_single_tariff(session, tariff_in, changed_time)
        await session.flush()

        tariff = await select_single_tariff(session, tariff_in.tariff_id)
        assert tariff is not None

        assert_class_instance_equality(
            Tariff, tariff, tariff_in, ignored_properties={"created_time", "changed_time", "version"}
        )
        assert tariff.created_time == datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC), "created_time doesn't update"
        assert tariff.changed_time == changed_time
        assert tariff.version == 1, "The DB has version=None so we roll straight to version 1"

        # Check the old tariff was archived before update
        assert (await session.execute(select(func.count()).select_from(ArchiveTariff))).scalar_one() == 1
        archive_data = (await session.execute(select(ArchiveTariff))).scalar_one()
        assert_class_instance_equality(
            Tariff,
            Tariff(
                tariff_id=1,
                name="tariff-1",
                dnsp_code="tariff-dnsp-code-1",
                currency_code=36,
                primacy=1,
                price_power_of_ten_multiplier=0,
                fsa_id=1,
                created_time=datetime(2000, 1, 1, tzinfo=UTC),
                changed_time=datetime(2023, 1, 2, 11, 1, 2, tzinfo=UTC),
            ),
            archive_data,
        )
        assert archive_data.archive_time is not None
        assert_nowish(archive_data.archive_time)
        assert archive_data.deleted_time is None

        await session.commit()

    # Check version increments
    async with generate_async_session(pg_base_config) as session:
        await update_single_tariff(session, tariff_in, changed_time)
        await session.flush()

        tariff = await select_single_tariff(session, tariff_in.tariff_id)
        assert tariff is not None and tariff.version == 2


@pytest.mark.anyio
async def test_update_single_tariff_component(pg_base_config):
    changed_time = datetime(2016, 6, 7, 14, 6, 8, tzinfo=UTC)
    async with generate_async_session(pg_base_config) as session:
        tc_in = generate_class_instance(TariffComponent)
        tc_in.tariff_component_id = 1
        await update_single_tariff_component(session, tc_in, changed_time)
        await session.flush()

        tc = await select_tariff_component_by_id(session, tc_in.tariff_component_id)
        assert tc is not None

        assert_class_instance_equality(
            TariffComponent, tc, tc_in, ignored_properties={"created_time", "changed_time", "version", "tariff_id"}
        )
        assert tc.created_time == datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC), "created_time doesn't update"
        assert tc.changed_time == changed_time
        assert tc.version == 1, "The DB has version=None so we roll straight to version 1"
        assert tc.tariff_id == 1, "This should NOT be updateable"

        # Check the old component was archived before update
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffComponent))).scalar_one() == 1
        archive_data = (await session.execute(select(ArchiveTariffComponent))).scalar_one()
        assert archive_data.archive_time is not None

        assert_class_instance_equality(
            TariffComponent,
            TariffComponent(
                tariff_component_id=1,
                tariff_id=1,
                role_flags=1,
                accumulation_behaviour=3,
                commodity=2,
                data_qualifier=2,
                flow_direction=1,
                kind=12,
                phase=0,
                power_of_ten_multiplier=3,
                uom=38,
                created_time=datetime(2000, 1, 1, tzinfo=UTC),
                changed_time=datetime(2022, 2, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=10))),
            ),
            archive_data,
        )
        assert_nowish(archive_data.archive_time)
        assert archive_data.deleted_time is None

        await session.commit()

    # Check version increments
    async with generate_async_session(pg_base_config) as session:
        await update_single_tariff_component(session, tc_in, changed_time)
        await session.flush()

        tc = await select_tariff_component_by_id(session, tc_in.tariff_component_id)
        assert tc is not None and tc.version == 2


@pytest.mark.anyio
async def test_insert_many_tariff_genrate_insert(pg_base_config):
    """Assert that we are able to successfully insert a valid TariffGeneratedRate into a db"""

    async with generate_async_session(pg_base_config) as session:
        rate_in: TariffGeneratedRate = generate_class_instance(
            TariffGeneratedRate, generate_relationships=False, site_group_id=1, tariff_id=1, tariff_component_id=1
        )
        # clean up generated instance to ensure it doesn't clash with base_config
        del rate_in.tariff_generated_rate_id

        inserted_ids = await insert_many_tariff_genrate(session, [rate_in])
        await session.commit()

        assert_list_type(int, inserted_ids, count=1)

    async with generate_async_session(pg_base_config) as session:
        rate_out = await _select_latest_tariff_generated_rate(session)
        assert rate_out.tariff_generated_rate_id == inserted_ids[0]

        assert_class_instance_equality(
            TariffGeneratedRate,
            rate_in,
            rate_out,
            ignored_properties={"tariff_generated_rate_id", "created_time"},
        )

        # created_time should be now as this is an insert, changed_time should match what was put in
        assert_nowish(rate_out.created_time)
        assert_datetime_equal(rate_in.changed_time, rate_out.changed_time)

        # No archive
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 0

        rate_in_1 = generate_class_instance(
            TariffGeneratedRate,
            site_group_id=1,
            tariff_id=1,
            tariff_component_id=1,
            start_time=rate_in.start_time + timedelta(seconds=1),
        )
        rate_in_2 = generate_class_instance(
            TariffGeneratedRate,
            site_group_id=1,
            tariff_id=1,
            tariff_component_id=1,
            start_time=rate_in.start_time + timedelta(seconds=2),
        )

        # Rerun as a sanity check to catch any weird conflict errors
        inserted_ids_1 = await insert_many_tariff_genrate(session, [rate_in_1, rate_in_2])
        assert_list_type(int, inserted_ids_1, count=2)

        assert inserted_ids[0] not in inserted_ids_1, "These should be new "

        # Re-inserting will not update - this will be a fresh record
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 0


@pytest.mark.anyio
async def test_insert_many_tariff_genrate_overlapping_time_ranges(pg_base_config):
    """Assert that we are able to successfully insert a TariffGeneratedRate whose time range overlaps an existing
    record, provided it doesn't share the exact same (tariff_component_id, start_time, site_group_id)"""

    async with generate_async_session(pg_base_config) as session:
        original_rate = await _select_latest_tariff_generated_rate(session)
        cloned_original_rate = clone_class_instance(
            original_rate, ignored_properties={"tariff", "site_group", "tariff_component"}
        )

        # clean up generated instance to ensure it doesn't clash with base_config
        rate_to_insert: TariffGeneratedRate = clone_class_instance(
            original_rate,
            ignored_properties={"tariff_generated_rate_id", "created_time", "site_group", "tariff", "tariff_component"},
        )
        rate_to_insert.price_pow10_encoded += 123
        rate_to_insert.changed_time = datetime(2026, 1, 3, tzinfo=UTC)
        rate_to_insert.created_time = datetime(2027, 1, 3, tzinfo=UTC)  # This shouldn't do anything
        rate_to_insert.start_time = original_rate.start_time + timedelta(seconds=1)  # avoid the unique constraint

        inserted_ids = await insert_many_tariff_genrate(session, [rate_to_insert])
        await session.commit()

        assert_list_type(int, inserted_ids, count=1)

    # Check the original rate in the DB remains unchanged and that a new record was created
    async with generate_async_session(pg_base_config) as session:
        rate_after_insert = await _select_tariff_generated_rate_by_id(
            session, cloned_original_rate.tariff_generated_rate_id
        )
        inserted_rate = await _select_tariff_generated_rate_by_id(session, inserted_ids[0])
        assert inserted_rate is not None

        # Old rate - no change
        assert_class_instance_equality(
            TariffGeneratedRate,
            cloned_original_rate,
            rate_after_insert,
        )

        # New rate - inserted
        assert_class_instance_equality(
            TariffGeneratedRate,
            rate_to_insert,
            inserted_rate,
            ignored_properties={"tariff_generated_rate_id", "created_time"},
        )
        assert_nowish(inserted_rate.created_time)

        # Nothing in the archive
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 0


@pytest.mark.anyio
async def test_insert_many_tariff_genrate_collision_raises(pg_base_config):
    """Assert that inserting a TariffGeneratedRate that collides on (tariff_component_id, start_time,
    site_group_id) with an existing record raises an IntegrityError and leaves the DB untouched."""

    async with generate_async_session(pg_base_config) as session:
        original_rate = await _select_latest_tariff_generated_rate(session)
        cloned_original_rate = clone_class_instance(
            original_rate, ignored_properties={"tariff", "site_group", "tariff_component"}
        )

        # Shares the same (tariff_component_id, start_time, site_group_id) as original_rate
        colliding_rate: TariffGeneratedRate = clone_class_instance(
            original_rate,
            ignored_properties={"tariff_generated_rate_id", "created_time", "site_group", "tariff", "tariff_component"},
        )
        colliding_rate.price_pow10_encoded += 123

        with pytest.raises(IntegrityError):
            await insert_many_tariff_genrate(session, [colliding_rate])

        await session.rollback()

    # Nothing should have been written to the DB (including the archive)
    async with generate_async_session(pg_base_config) as session:
        rate_after_insert = await _select_tariff_generated_rate_by_id(
            session, cloned_original_rate.tariff_generated_rate_id
        )
        assert_class_instance_equality(TariffGeneratedRate, cloned_original_rate, rate_after_insert)

        assert (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one() == 7, (
            "base_config.sql seeds 7 rates - none should have been added"
        )
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 0


@pytest.mark.anyio
async def test_insert_many_tariff_genrate_ignore_collisions_empty(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        assert await insert_many_tariff_genrate_ignore_collisions(session, []) == []


@pytest.mark.anyio
async def test_insert_many_tariff_genrate_ignore_collisions(pg_base_config):
    """Mix of colliding/new/duplicated-within-batch rates - checks the returned IDs preserve 1-1 correspondence"""

    async with generate_async_session(pg_base_config) as session:
        original_rate = await _select_latest_tariff_generated_rate(session)

        colliding_rate: TariffGeneratedRate = clone_class_instance(
            original_rate,
            ignored_properties={"tariff_generated_rate_id", "created_time", "site_group", "tariff", "tariff_component"},
        )
        colliding_rate.price_pow10_encoded += 123  # Collides with original_rate - shouldn't be inserted

        new_rate_1: TariffGeneratedRate = clone_class_instance(
            colliding_rate, ignored_properties={"site_group", "tariff", "tariff_component"}
        )
        new_rate_1.start_time = original_rate.start_time + timedelta(seconds=1)  # Doesn't collide

        new_rate_2: TariffGeneratedRate = clone_class_instance(
            colliding_rate, ignored_properties={"site_group", "tariff", "tariff_component"}
        )
        new_rate_2.start_time = original_rate.start_time + timedelta(seconds=2)  # Doesn't collide

        result = await insert_many_tariff_genrate_ignore_collisions(session, [colliding_rate, new_rate_1, new_rate_2])
        await session.commit()

        assert len(result) == 3
        assert result[0] is None
        assert isinstance(result[1], int)
        assert isinstance(result[2], int)
        assert result[1] != result[2]

    async with generate_async_session(pg_base_config) as session:
        assert (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one() == 9, (
            "The 7 seeded rates plus the 2 newly inserted (non-colliding) rates"
        )
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 0


@pytest.mark.anyio
async def test_cancel_colliding_tariff_generated_rates_empty(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        await cancel_colliding_tariff_generated_rates(session, [], datetime(2028, 4, 1, tzinfo=UTC))
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 0


@pytest.mark.anyio
async def test_cancel_colliding_tariff_generated_rates(pg_base_config):
    """Only rates that collide on (tariff_component_id, start_time, site_group_id) should be cancelled"""

    deleted_time = datetime(2028, 4, 1, tzinfo=UTC)
    async with generate_async_session(pg_base_config) as session:
        rate_1 = await _select_tariff_generated_rate_by_id(session, 1)  # Will collide
        rate_2 = await _select_tariff_generated_rate_by_id(session, 2)  # Will collide
        rate_4 = await _select_tariff_generated_rate_by_id(session, 4)  # Will NOT collide (diff site_group_id)
        assert rate_1 is not None and rate_2 is not None and rate_4 is not None

        colliding_1 = clone_class_instance(rate_1, ignored_properties={"tariff", "site_group", "tariff_component"})
        colliding_2 = clone_class_instance(rate_2, ignored_properties={"tariff", "site_group", "tariff_component"})
        non_colliding = clone_class_instance(rate_4, ignored_properties={"tariff", "site_group", "tariff_component"})
        non_colliding.site_group_id = 99  # No existing rate matches this combination

        await cancel_colliding_tariff_generated_rates(session, [colliding_1, colliding_2, non_colliding], deleted_time)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        remaining_ids = (await session.execute(select(TariffGeneratedRate.tariff_generated_rate_id))).scalars().all()
        assert sorted(remaining_ids) == [3, 4, 5, 6, 7], "Only rates 1 and 2 should have been cancelled"

        archive_records = (await session.execute(select(ArchiveTariffGeneratedRate))).scalars().all()
        assert len(archive_records) == 2
        assert sorted([a.tariff_generated_rate_id for a in archive_records]) == [1, 2]
        assert all(a.deleted_time == deleted_time for a in archive_records)


@pytest.mark.parametrize(
    "tariff_component_ids, expected_result",
    [
        ([], {}),
        ([99], {}),
        ([99, 98], {}),
        ([99, 98], {}),
        ([1], {1: 1}),
        ([1, 2, 3, 4], {1: 1, 2: 1, 3: 1, 4: 2}),
        ([1, 2, 3], {1: 1, 2: 1, 3: 1}),
        ([4, 1], {1: 1, 4: 2}),
        ([1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 4, 4], {1: 1, 2: 1, 3: 1, 4: 2}),
    ],
)
@pytest.mark.anyio
async def test_select_tariff_ids_for_component_ids(
    pg_base_config, tariff_component_ids: list[int], expected_result: dict[int, int]
):
    async with generate_async_session(pg_base_config) as session:
        result = await select_tariff_ids_for_component_ids(session, tariff_component_ids)
        assert_dict_type(int, int, result, count=len(expected_result))
        assert result == expected_result


@pytest.mark.anyio
async def test_select_single_tariff_generated_rate(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        assert (await select_single_tariff_generated_rate(session, 99)) is None

        rate1 = await select_single_tariff_generated_rate(session, 1)
        assert isinstance(rate1, TariffGeneratedRate)
        assert rate1.site_group_id == 2
        assert rate1.price_pow10_encoded == 1111
        assert rate1.price_pow10_encoded_block_1 == 1001

        rate4 = await select_single_tariff_generated_rate(session, 4)
        assert isinstance(rate4, TariffGeneratedRate)
        assert rate4.site_group_id == 4
        assert rate4.price_pow10_encoded == 4444
        assert rate4.price_pow10_encoded_block_1 is None


@pytest.mark.parametrize(
    "tariff_generated_rate_id, expected_deleted_price",
    [
        (99, None),
        (1, 1111),
        (2, 2222),
        (4, 4444),
        (6, 6666),
        (7, 7777),
    ],
)
@pytest.mark.anyio
async def test_cancel_tariff_generated_rate(pg_base_config, tariff_generated_rate_id, expected_deleted_price):
    deleted_time = datetime(2028, 4, 1, tzinfo=UTC)
    async with generate_async_session(pg_base_config) as session:
        await cancel_tariff_generated_rate(session, tariff_generated_rate_id, deleted_time)

        # Record not in active table anymore
        assert (
            await session.execute(
                select(func.count())
                .select_from(TariffGeneratedRate)
                .where(TariffGeneratedRate.tariff_generated_rate_id == tariff_generated_rate_id)
            )
        ).scalar_one() == 0

        # Record archived correctly (if it existed)
        archive_records = (await session.execute(select(ArchiveTariffGeneratedRate))).scalars().all()
        if expected_deleted_price is None:
            assert len(archive_records) == 0
        else:
            assert len(archive_records) == 1
            rec = archive_records[0]
            assert rec.tariff_generated_rate_id == tariff_generated_rate_id
            assert rec.deleted_time == deleted_time
            assert rec.price_pow10_encoded == expected_deleted_price


@pytest.mark.parametrize(
    "tariff_component_id, expected_deleted_prices",
    [
        (99, None),
        (1, [1111, 2222, 3333, 4444, 5555]),
        (2, [6666]),
        (3, []),
    ],
)
@pytest.mark.anyio
async def test_cancel_and_delete_tariff_component(
    pg_base_config, tariff_component_id: int, expected_deleted_prices: list[int] | None
):
    deleted_time = datetime(2028, 4, 1, tzinfo=UTC)
    async with generate_async_session(pg_base_config) as session:
        await cancel_and_delete_tariff_component(session, tariff_component_id, deleted_time)

        # Record not in active table anymore
        assert (
            await session.execute(
                select(func.count())
                .select_from(TariffComponent)
                .where(TariffComponent.tariff_component_id == tariff_component_id)
            )
        ).scalar_one() == 0

        # Record prices not in active table anymore
        if expected_deleted_prices:
            assert (
                await session.execute(
                    select(func.count())
                    .select_from(TariffGeneratedRate)
                    .where(TariffGeneratedRate.price_pow10_encoded.in_(expected_deleted_prices))
                )
            ).scalar_one() == 0

        # Record archived correctly (if it existed)
        archive_tcs = (await session.execute(select(ArchiveTariffComponent))).scalars().all()
        archive_rates = (await session.execute(select(ArchiveTariffGeneratedRate))).scalars().all()
        if expected_deleted_prices is None:
            assert len(archive_tcs) == 0
            assert len(archive_rates) == 0
        else:
            assert len(archive_tcs) == 1
            rec = archive_tcs[0]
            assert rec.tariff_component_id == tariff_component_id
            assert rec.deleted_time == deleted_time

            assert len(archive_rates) == len(expected_deleted_prices)
            assert sorted(expected_deleted_prices) == sorted([a.price_pow10_encoded for a in archive_rates])
            assert all([a.deleted_time == deleted_time for a in archive_rates])


@pytest.mark.parametrize(
    "tariff_component_id,start_time_since,start_time_until,site_group_ids,start,limit,expected_ids,expected_count",
    [
        (1, None, None, None, 0, 99, [1, 2, 3, 4, 5], 5),
        (1, None, None, None, 1, 2, [2, 3], 5),  # paging
        (2, None, None, None, 0, 100, [6], 1),
        (3, None, None, None, 0, 100, [], 0),
        (1, datetime(2000, 1, 1, tzinfo=UTC), datetime(2001, 1, 1, tzinfo=UTC), None, 0, 100, [], 0),
        (
            1,
            datetime(2000, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, tzinfo=UTC),
            None,
            0,
            100,
            [1, 2, 3, 4, 5],
            5,
        ),
        (
            1,
            datetime(2022, 3, 4, 15, 0, 0, tzinfo=UTC),
            datetime(2022, 3, 4, 15, 0, 33, tzinfo=UTC),
            None,
            0,
            100,
            [1, 2, 4, 5],
            4,
        ),
        (1, None, None, {1, 2, 99}, 0, 99, [1, 2, 3], 3),
        (1, None, None, {1, 99}, 0, 99, [], 0),
        (1, None, None, set(), 0, 99, [], 0),
        (
            1,
            datetime(2022, 3, 4, 15, 0, 0, tzinfo=UTC),
            datetime(2022, 3, 4, 15, 0, 33, tzinfo=UTC),
            {1, 2},
            0,
            100,
            [1, 2],
            2,
        ),
        (99, None, None, None, 0, 99, [], 0),
    ],
)
@pytest.mark.anyio
async def test_select_count_filtered_tariff_generated_rates(
    pg_base_config,
    tariff_component_id: int,
    start_time_since: datetime | None,
    start_time_until: datetime | None,
    site_group_ids: set[int] | None,
    start: int,
    limit: int,
    expected_ids: list[int],
    expected_count: int,
):
    async with generate_async_session(pg_base_config) as session:
        actual_rates = await select_filtered_tariff_generated_rates(
            session,
            tariff_component_id,
            start_time_since=start_time_since,
            start_time_until=start_time_until,
            site_group_ids=site_group_ids,
            start=start,
            limit=limit,
        )
        actual_count = await count_filtered_tariff_generated_rates(
            session,
            tariff_component_id,
            start_time_since=start_time_since,
            start_time_until=start_time_until,
            site_group_ids=site_group_ids,
        )

        assert expected_ids == [r.tariff_generated_rate_id for r in actual_rates]
        assert_list_type(TariffGeneratedRate, actual_rates, count=len(expected_ids))
        assert actual_count == expected_count
