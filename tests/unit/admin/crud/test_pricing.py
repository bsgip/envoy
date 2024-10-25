from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import select

from envoy.admin.crud.pricing import insert_single_tariff, update_single_tariff, upsert_many_tariff_genrate
from envoy.server.crud.pricing import select_single_tariff
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


async def _select_latest_tariff_generated_rate(session) -> TariffGeneratedRate:
    stmt = select(TariffGeneratedRate).order_by(TariffGeneratedRate.tariff_generated_rate_id.desc()).limit(1)
    resp = await session.execute(stmt)
    return resp.scalar_one()


@pytest.mark.anyio
async def test_insert_single_tariff(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        tariff_in = generate_class_instance(Tariff)
        tariff_in.tariff_id = None
        await insert_single_tariff(session, tariff_in)

        await session.flush()

        assert tariff_in.tariff_id == 1
        tariff = await select_single_tariff(session, tariff_in.tariff_id)

        assert_class_instance_equality(Tariff, tariff, tariff_in)
        assert_nowish(tariff.created_time)


@pytest.mark.anyio
async def test_update_single_tariff(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        tariff_in = generate_class_instance(Tariff)
        tariff_in.tariff_id = 1
        await update_single_tariff(session, tariff_in)
        await session.flush()

        tariff = await select_single_tariff(session, tariff_in.tariff_id)

        assert_class_instance_equality(Tariff, tariff, tariff_in, ignored_properties={"created_time"})
        assert tariff.created_time == datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc), "created_time doesn't update"


@pytest.mark.anyio
async def test_upsert_many_tariff_genrate_insert(pg_base_config):
    """Assert that we are able to successfully insert a valid TariffGeneratedRate into a db"""

    async with generate_async_session(pg_base_config) as session:
        doe_in: TariffGeneratedRate = generate_class_instance(
            TariffGeneratedRate, generate_relationships=False, site_id=1, tariff_id=1
        )
        # clean up generated instance to ensure it doesn't clash with base_config
        del doe_in.tariff_generated_rate_id

        await upsert_many_tariff_genrate(session, [doe_in])
        await session.flush()

        doe_out = await _select_latest_tariff_generated_rate(session)

        assert_class_instance_equality(
            TariffGeneratedRate,
            doe_out,
            doe_in,
            ignored_properties={"tariff_generated_rate_id", "created_time"},
        )

        # created_time should be now as this is an insert, changed_time should match what was put in
        assert_nowish(doe_out.created_time)
        assert_datetime_equal(doe_out.changed_time, doe_out.changed_time)

        doe_in_1 = generate_class_instance(
            TariffGeneratedRate, site_id=1, tariff_id=1, start_time=doe_in.start_time + timedelta(seconds=1)
        )

        await upsert_many_tariff_genrate(session, [doe_in, doe_in_1])


@pytest.mark.anyio
async def test_upsert_many_tariff_genrate_update(pg_base_config):
    """Assert that we are able to successfully update a valid TariffGeneratedRate in the db"""

    async with generate_async_session(pg_base_config) as session:
        original_rate = await _select_latest_tariff_generated_rate(session)
        original_id = original_rate.tariff_generated_rate_id
        original_created_time = original_rate.created_time

        # clean up generated instance to ensure it doesn't clash with base_config
        rate_to_update: TariffGeneratedRate = clone_class_instance(
            original_rate, ignored_properties={"tariff_generated_rate_id", "created_time", "site", "tariff"}
        )
        rate_to_update.import_active_price += Decimal("99.1")
        rate_to_update.export_active_price += Decimal("99.2")
        rate_to_update.import_reactive_price += Decimal("98.1")
        rate_to_update.export_reactive_price += Decimal("98.2")
        rate_to_update.changed_time = datetime(2026, 1, 3, tzinfo=timezone.utc)
        rate_to_update.created_time = datetime(2027, 1, 3, tzinfo=timezone.utc)  # This shouldn't do anything

        await upsert_many_tariff_genrate(session, [rate_to_update])
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        rate_after_update = await _select_latest_tariff_generated_rate(session)

        # Created time stays the same. changed_time updates
        assert original_id == rate_after_update.tariff_generated_rate_id
        assert_class_instance_equality(
            TariffGeneratedRate,
            rate_to_update,
            rate_after_update,
            ignored_properties={"tariff_generated_rate_id", "created_time", "site", "tariff"},
        )
        assert_datetime_equal(original_created_time, rate_after_update.created_time)
