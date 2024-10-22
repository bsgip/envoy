import json
from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest, TariffResponse
from envoy_schema.admin.schema.uri import TariffCreateUri, TariffGeneratedRateCreateUri, TariffUpdateUri
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.server.model.tariff import TariffGeneratedRate


@pytest.mark.anyio
async def test_get_all_tariffs(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(TariffCreateUri, params={"limit": 3})
    assert resp.status_code == HTTPStatus.OK
    tariff_resp_list = [TariffResponse(**d) for d in json.loads(resp.content)]
    assert len(tariff_resp_list) == 3


@pytest.mark.anyio
async def test_get_single_tariff(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(TariffUpdateUri.format(tariff_id=1))
    assert resp.status_code == HTTPStatus.OK
    tariff_resp = TariffResponse(**json.loads(resp.content))
    assert tariff_resp.tariff_id == 1


@pytest.mark.anyio
async def test_create_tariff(admin_client_auth: AsyncClient):
    tariff = generate_class_instance(TariffRequest)
    tariff.currency_code = 36
    resp = await admin_client_auth.post(TariffCreateUri, json=tariff.model_dump())

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.anyio
async def test_update_tariff(admin_client_auth: AsyncClient):
    tariff = generate_class_instance(TariffRequest)
    tariff.currency_code = 36
    resp = await admin_client_auth.put(TariffUpdateUri.format(tariff_id=1), json=tariff.model_dump())

    assert resp.status_code == HTTPStatus.OK


@pytest.mark.anyio
async def test_create_tariff_genrates(admin_client_auth: AsyncClient):
    tariff_genrate = generate_class_instance(TariffGeneratedRateRequest, tariff_id=1, site_id=1)

    tariff_genrate_1 = generate_class_instance(TariffGeneratedRateRequest, tariff_id=2, site_id=2)

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{tariff_genrate.model_dump_json()}, {tariff_genrate_1.model_dump_json()}]",
    )

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.anyio
async def test_update_tariff_genrate_calculation_log(pg_base_config, admin_client_auth: AsyncClient):
    """Checks that updating a price will update in place and not insert a new record"""
    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(TariffGeneratedRate)
        resp = await session.execute(stmt)
        initial_count = resp.scalar_one()

    # This should be updating tariff_generated_rate_id 1
    updated_rate = TariffGeneratedRateRequest(
        tariff_id=1,
        site_id=1,
        start_time=datetime(2022, 3, 5, 1, 2, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=1113,
        calculation_log_id=3,
        import_active_price=1,
        export_active_price=2,
        import_reactive_price=3,
        export_reactive_price=4,
    )

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{updated_rate.model_dump_json()}]",
    )

    assert resp.status_code == HTTPStatus.CREATED

    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(TariffGeneratedRate)
        resp = await session.execute(stmt)
        after_count = resp.scalar_one()

        assert initial_count == after_count, "This should've been an update, not an insert"

        stmt = select(TariffGeneratedRate).where(TariffGeneratedRate.calculation_log_id == 3)
        db_rate = (await session.execute(stmt)).scalar_one()

        assert db_rate.calculation_log_id == updated_rate.calculation_log_id
        assert db_rate.start_time == updated_rate.start_time
        assert db_rate.duration_seconds == updated_rate.duration_seconds
        assert_nowish(db_rate.changed_time)
        assert db_rate.import_active_price == updated_rate.import_active_price
        assert db_rate.export_active_price == updated_rate.export_active_price
        assert db_rate.import_reactive_price == updated_rate.import_reactive_price
        assert db_rate.export_reactive_price == updated_rate.export_reactive_price
