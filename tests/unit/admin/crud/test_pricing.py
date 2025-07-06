from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import func, select

from envoy.admin.crud.pricing import insert_single_tariff, update_single_tariff, upsert_many_tariff_genrate
from envoy.server.crud.pricing import select_single_tariff
from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffGeneratedRate
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

        # No archival on insert
        assert (await session.execute(select(func.count()).select_from(ArchiveTariff))).scalar_one() == 0


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
                created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                changed_time=datetime(2023, 1, 2, 11, 1, 2, tzinfo=timezone.utc),
                fsa_id=1,
            ),
            archive_data,
        )
        assert_nowish(archive_data.archive_time)
        assert archive_data.deleted_time is None


@pytest.mark.anyio
async def test_upsert_many_tariff_genrate_insert(pg_base_config):
    """Assert that we are able to successfully insert a valid TariffGeneratedRate into a db"""

    deleted_time = datetime(2022, 1, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        doe_in: TariffGeneratedRate = generate_class_instance(
            TariffGeneratedRate, generate_relationships=False, site_id=1, tariff_id=1
        )
        # clean up generated instance to ensure it doesn't clash with base_config
        del doe_in.tariff_generated_rate_id

        await upsert_many_tariff_genrate(session, [doe_in], deleted_time)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
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

        # No archive on insert
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 0

        doe_in_1 = generate_class_instance(
            TariffGeneratedRate, site_id=1, tariff_id=1, start_time=doe_in.start_time + timedelta(seconds=1)
        )

        # Rerun as a sanity check to catch any weird conflict errors
        await upsert_many_tariff_genrate(session, [doe_in, doe_in_1], deleted_time)

        # Re-inserting will generate an archived value
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 1


@pytest.mark.anyio
async def test_upsert_many_tariff_genrate_update(pg_base_config):
    """Assert that we are able to successfully update a valid TariffGeneratedRate in the db"""

    deleted_time = datetime(2022, 1, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        original_rate = await _select_latest_tariff_generated_rate(session)
        cloned_original_rate = clone_class_instance(original_rate, ignored_properties={"tariff", "site"})

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

        await upsert_many_tariff_genrate(session, [rate_to_update], deleted_time)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        rate_after_update = await _select_latest_tariff_generated_rate(session)

        # This was a delete and new insert - created time changes
        assert_class_instance_equality(
            TariffGeneratedRate,
            rate_to_update,
            rate_after_update,
            ignored_properties={"tariff_generated_rate_id", "created_time", "site", "tariff"},
        )
        assert_nowish(rate_after_update.created_time)

        # Old rate should've been archived
        assert (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one() == 1
        archive_data = (await session.execute(select(ArchiveTariffGeneratedRate))).scalar_one()

        assert_class_instance_equality(
            TariffGeneratedRate, cloned_original_rate, archive_data, ignored_properties={"tariff", "site"}
        )
        assert_nowish(archive_data.archive_time)
        assert archive_data.deleted_time == deleted_time
