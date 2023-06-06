from datetime import timedelta
import pytest

from sqlalchemy import select

from envoy.admin.crud.pricing import (
    insert_single_tariff,
    update_single_tariff,
    upsert_many_tariff_genrate,
)
from envoy.server.crud.pricing import select_single_tariff
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


from tests.postgres_testing import generate_async_session
from tests.data.fake.generator import generate_class_instance, assert_class_instance_equality


async def _select_latest_tariff_generated_rate(session):
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


@pytest.mark.anyio
async def test_update_single_tariff(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        tariff_in = generate_class_instance(Tariff)
        tariff_in.tariff_id = 1
        await update_single_tariff(session, tariff_in)
        await session.flush()

        tariff = await select_single_tariff(session, tariff_in.tariff_id)

        assert_class_instance_equality(Tariff, tariff, tariff_in)


@pytest.mark.anyio
async def test_upsert_many_tariff_genrate(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        tariff_genrate_in = generate_class_instance(TariffGeneratedRate)
        tariff_genrate_in.tariff_id = 1
        tariff_genrate_in.site_id = 1
        del tariff_genrate_in.site
        del tariff_genrate_in.tariff
        tariff_genrate_in.tariff_generated_rate_id = None
        await upsert_many_tariff_genrate(session, [tariff_genrate_in])

        tariff_genrate = await _select_latest_tariff_generated_rate(session)

        assert_class_instance_equality(
            TariffGeneratedRate, tariff_genrate, tariff_genrate_in, ignored_properties={"tariff_generated_rate_id"}
        )

        tariff_genrate_in_1 = generate_class_instance(TariffGeneratedRate)
        tariff_genrate_in_1.tariff_id = 1
        tariff_genrate_in_1.site_id = 1
        tariff_genrate_in_1.start_time = tariff_genrate_in_1.start_time + timedelta(seconds=1)

        await upsert_many_tariff_genrate(session, [tariff_genrate_in, tariff_genrate_in_1])
