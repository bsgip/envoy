import json
from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.base import BatchCreateResponse
from envoy_schema.admin.schema.pricing import (
    TariffComponentRequest,
    TariffComponentResponse,
    TariffGeneratedRateRequest,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.admin.schema.uri import (
    TariffComponentCreateUri,
    TariffComponentUpdateUri,
    TariffCreateUri,
    TariffGeneratedRateCreateUri,
    TariffUpdateUri,
)
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
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
async def test_create_tariff_with_fetch(admin_client_auth: AsyncClient):
    """Can we create a Tariff and then refetch the thing we just created"""
    tariff = generate_class_instance(TariffRequest)
    resp = await admin_client_auth.post(TariffCreateUri, json=tariff.model_dump())

    assert resp.status_code == HTTPStatus.CREATED

    batch_resp = BatchCreateResponse(**json.loads(resp.content))
    assert resp.headers["Location"] == TariffUpdateUri.format(tariff_id=batch_resp.ids[0])

    # After creating - try and fetch it back to see if matches what we sent
    resp = await admin_client_auth.get(resp.headers["Location"])
    assert resp.status_code == HTTPStatus.OK
    tariff_resp = TariffResponse(**json.loads(resp.content))

    assert_class_instance_equality(TariffRequest, tariff, tariff_resp)
    assert tariff_resp.tariff_id == batch_resp.ids[0]
    assert_nowish(tariff_resp.created_time)
    assert_nowish(tariff_resp.changed_time)


@pytest.mark.anyio
async def test_update_tariff(admin_client_auth: AsyncClient):
    tariff = generate_class_instance(TariffRequest)
    tariff.currency_code = 36
    resp = await admin_client_auth.put(TariffUpdateUri.format(tariff_id=1), json=tariff.model_dump())

    assert resp.status_code == HTTPStatus.OK


@pytest.mark.parametrize("tariff_id", [1, 2, 3])
@pytest.mark.anyio
async def test_create_tariff_component_with_fetch(admin_client_auth: AsyncClient, tariff_id: int):
    """Can we create a TariffComponent and then refetch the thing we just created"""

    tc = generate_class_instance(TariffComponentRequest, tariff_id=tariff_id)
    resp = await admin_client_auth.post(TariffComponentCreateUri, json=tc.model_dump())

    assert resp.status_code == HTTPStatus.CREATED

    batch_resp = BatchCreateResponse(**json.loads(resp.content))
    assert resp.headers["Location"] == TariffComponentUpdateUri.format(tariff_component_id=batch_resp.ids[0])

    # After creating - try and fetch it back to see if matches what we sent
    resp = await admin_client_auth.get(resp.headers["Location"])
    assert resp.status_code == HTTPStatus.OK
    tc_resp = TariffComponentResponse(**json.loads(resp.content))

    assert_class_instance_equality(TariffComponentRequest, tc, tc_resp)
    assert tc_resp.tariff_component_id == batch_resp.ids[0]
    assert_nowish(tc_resp.created_time)
    assert_nowish(tc_resp.changed_time)


@pytest.mark.anyio
async def test_create_tariff_component_bad_tariff_id(admin_client_auth: AsyncClient):
    """Trying to create a TariffComponent with a bad Tariff ID returns a BadRequest"""

    tc = generate_class_instance(TariffComponentRequest, tariff_id=99)
    resp = await admin_client_auth.post(TariffComponentCreateUri, json=tc.model_dump())
    assert resp.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.anyio
async def test_create_tariff_genrates(admin_client_auth: AsyncClient):
    tariff_genrate = generate_class_instance(TariffGeneratedRateRequest, tariff_component_id=1, site_id=1)

    tariff_genrate_1 = generate_class_instance(TariffGeneratedRateRequest, tariff_component_id=2, site_id=2)

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{tariff_genrate.model_dump_json()}, {tariff_genrate_1.model_dump_json()}]",
        headers={"Content-Type": "application/json"},
    )

    assert resp.status_code == HTTPStatus.CREATED
    rate_resp = BatchCreateResponse(**json.loads(resp.content))

    assert rate_resp.ids == [8, 9], "We know that the DB sequence is set to 8 in base_config.sql"


@pytest.mark.anyio
async def test_no_update_tariff_genrate(pg_base_config, admin_client_auth: AsyncClient):
    """Checks that inserting a price will never update an existing record"""

    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(TariffGeneratedRate)
        resp = await session.execute(stmt)
        initial_count = resp.scalar_one()

    # This should overlap tariff_generated_rate_id 1
    updated_rate = TariffGeneratedRateRequest(
        tariff_component_id=1,
        site_id=1,
        start_time=datetime(2022, 3, 5, 1, 2, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=1113,
        calculation_log_id=3,
        price_pow10_encoded=998877,
    )

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{updated_rate.model_dump_json()}]",
        headers={"Content-Type": "application/json"},
    )

    assert resp.status_code == HTTPStatus.CREATED
    rate_resp = BatchCreateResponse(**json.loads(resp.content))

    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(TariffGeneratedRate)
        resp = await session.execute(stmt)
        after_count = resp.scalar_one()

        assert (initial_count + 1) == after_count, "This should've been an insert"

        stmt = select(TariffGeneratedRate).where(TariffGeneratedRate.calculation_log_id == 3)
        db_rate = (await session.execute(stmt)).scalar_one()

        assert db_rate.tariff_generated_rate_id == rate_resp.ids[0]
        assert db_rate.calculation_log_id == updated_rate.calculation_log_id
        assert db_rate.start_time == updated_rate.start_time
        assert db_rate.duration_seconds == updated_rate.duration_seconds
        assert_nowish(db_rate.changed_time)
        assert_nowish(db_rate.created_time)  # Updated record was archived. This is a newly inserted record
        assert db_rate.price_pow10_encoded == updated_rate.price_pow10_encoded

        assert (
            await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))
        ).scalar_one() == 0, "This should be an insert - no changes in the archive"
