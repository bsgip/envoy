import json
from datetime import datetime
from http import HTTPStatus
from typing import Optional
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
    TariffGeneratedRateResponse,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.admin.schema.uri import (
    TariffComponentCreateUri,
    TariffComponentUpdateUri,
    TariffCreateUri,
    TariffGeneratedRateCreateUri,
    TariffGeneratedRateUpdateUri,
    TariffUpdateUri,
)
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffComponent, ArchiveTariffGeneratedRate
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


@pytest.mark.parametrize(
    "tariff_id, new_values, expected_status",
    [
        (1, generate_class_instance(TariffRequest), HTTPStatus.NO_CONTENT),
        (3, generate_class_instance(TariffRequest, optional_is_none=True), HTTPStatus.NO_CONTENT),
        (99, generate_class_instance(TariffRequest), HTTPStatus.NOT_FOUND),
    ],
)
@pytest.mark.anyio
async def test_update_tariff(
    pg_base_config,
    admin_client_auth: AsyncClient,
    tariff_id: int,
    new_values: TariffRequest,
    expected_status: HTTPStatus,
):
    """Can we update a Tariff and then refetch the thing we just updated."""

    uri = TariffUpdateUri.format(tariff_id=tariff_id)
    resp = await admin_client_auth.put(uri, json=new_values.model_dump())
    assert resp.status_code == expected_status

    if resp.status_code == HTTPStatus.NO_CONTENT:
        # After creating - try and fetch it back to see if matches what we sent
        resp = await admin_client_auth.get(uri)
        assert resp.status_code == HTTPStatus.OK
        tariff_resp = TariffResponse(**json.loads(resp.content))

        assert_class_instance_equality(TariffRequest, new_values, tariff_resp)
        assert_nowish(tariff_resp.changed_time)

        # Check the archive has 1 entry
        async with generate_async_session(pg_base_config) as session:
            db_count = await session.execute(select(func.count()).select_from(ArchiveTariff))
            assert db_count.scalar_one() == 1
    else:
        # Check the archive is empty
        async with generate_async_session(pg_base_config) as session:
            db_count = await session.execute(select(func.count()).select_from(ArchiveTariff))
            assert db_count.scalar_one() == 0


@pytest.mark.parametrize(
    "tariff_component_id, expected_status", [(1, HTTPStatus.OK), (4, HTTPStatus.OK), (99, HTTPStatus.NOT_FOUND)]
)
@pytest.mark.anyio
async def test_fetch_tariff_component(
    admin_client_auth: AsyncClient, tariff_component_id: int, expected_status: HTTPStatus
):
    resp = await admin_client_auth.get(TariffComponentUpdateUri.format(tariff_component_id=tariff_component_id))
    assert resp.status_code == expected_status

    if resp.status_code == HTTPStatus.OK:
        tc_resp = TariffComponentResponse(**json.loads(resp.content))
        assert tc_resp.tariff_component_id == tariff_component_id


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


@pytest.mark.parametrize(
    "tariff_component_id, new_values, expected_status",
    [
        (1, generate_class_instance(TariffComponentRequest, tariff_id=99), HTTPStatus.NO_CONTENT),
        (1, generate_class_instance(TariffComponentRequest, tariff_id=1), HTTPStatus.NO_CONTENT),
        (3, generate_class_instance(TariffComponentRequest, optional_is_none=True), HTTPStatus.NO_CONTENT),
        (4, generate_class_instance(TariffComponentRequest, optional_is_none=True), HTTPStatus.NO_CONTENT),
        (99, generate_class_instance(TariffComponentRequest), HTTPStatus.NOT_FOUND),
    ],
)
@pytest.mark.anyio
async def test_update_tariff_component(
    pg_base_config,
    admin_client_auth: AsyncClient,
    tariff_component_id: int,
    new_values: TariffComponentRequest,
    expected_status: HTTPStatus,
):
    """Can we update a TariffComponent and then refetch the thing we just updated."""

    # Before doing anything - snapshot the original value
    uri = TariffComponentUpdateUri.format(tariff_component_id=tariff_component_id)
    resp = await admin_client_auth.get(uri)
    original_tc: Optional[TariffComponentResponse] = None
    if resp.status_code == HTTPStatus.OK:
        original_tc = TariffComponentResponse(**json.loads(resp.content))

    resp = await admin_client_auth.put(uri, json=new_values.model_dump())
    assert resp.status_code == expected_status

    if resp.status_code == HTTPStatus.NO_CONTENT:
        # Check the updates applied
        assert original_tc is not None

        # After creating - try and fetch it back to see if matches what we sent
        resp = await admin_client_auth.get(uri)
        assert resp.status_code == HTTPStatus.OK
        tc_resp = TariffComponentResponse(**json.loads(resp.content))

        assert_class_instance_equality(TariffComponentRequest, new_values, tc_resp, ignored_properties={"tariff_id"})

        assert tc_resp.tariff_id == original_tc.tariff_id
        assert_nowish(tc_resp.changed_time)

        # Check the archive has 1 entry
        async with generate_async_session(pg_base_config) as session:
            db_count = await session.execute(select(func.count()).select_from(ArchiveTariffComponent))
            assert db_count.scalar_one() == 1
    else:
        # Check the archive is empty
        async with generate_async_session(pg_base_config) as session:
            db_count = await session.execute(select(func.count()).select_from(ArchiveTariffComponent))
            assert db_count.scalar_one() == 0


@pytest.mark.anyio
async def test_create_tariff_genrates_with_fetch(admin_client_auth: AsyncClient):
    tariff_genrate_1 = generate_class_instance(
        TariffGeneratedRateRequest, seed=101, tariff_component_id=1, site_id=1, calculation_log_id=1
    )

    tariff_genrate_2 = generate_class_instance(
        TariffGeneratedRateRequest, seed=202, tariff_component_id=2, site_id=2, calculation_log_id=None
    )

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{tariff_genrate_1.model_dump_json()}, {tariff_genrate_2.model_dump_json()}]",
    )

    assert resp.status_code == HTTPStatus.CREATED
    rate_resp = BatchCreateResponse(**json.loads(resp.content))

    assert rate_resp.ids == [8, 9], "We know that the DB sequence is set to 8 in base_config.sql"

    for new_id, expected_genrate in zip(rate_resp.ids, [tariff_genrate_1, tariff_genrate_2]):
        # Now refetch each newly created record
        resp = await admin_client_auth.get(TariffGeneratedRateUpdateUri.format(tariff_generated_rate_id=new_id))
        assert resp.status_code == HTTPStatus.OK
        actual_genrate = TariffGeneratedRateResponse(**json.loads(resp.content))

        assert_class_instance_equality(TariffGeneratedRateRequest, expected_genrate, actual_genrate)
        assert actual_genrate.tariff_generated_rate_id == new_id
        assert_nowish(actual_genrate.created_time)
        assert_nowish(actual_genrate.changed_time)


@pytest.mark.parametrize(
    "tariff_generated_rate_id, expected_status", [(1, HTTPStatus.OK), (4, HTTPStatus.OK), (99, HTTPStatus.NOT_FOUND)]
)
@pytest.mark.anyio
async def test_fetch_tariff_generated_rate(
    admin_client_auth: AsyncClient, tariff_generated_rate_id: int, expected_status: HTTPStatus
):
    resp = await admin_client_auth.get(
        TariffGeneratedRateUpdateUri.format(tariff_generated_rate_id=tariff_generated_rate_id)
    )
    assert resp.status_code == expected_status

    if resp.status_code == HTTPStatus.OK:
        tc_resp = TariffGeneratedRateResponse(**json.loads(resp.content))
        assert tc_resp.tariff_generated_rate_id == tariff_generated_rate_id


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
