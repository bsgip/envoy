import json
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.pricing import (
    TariffGeneratedRateRequest,
    TariffPageResponse,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.admin.schema.uri import TariffGeneratedRateCreateUri, TariffListUri, TariffUpdateUri
from envoy_schema.server.schema.sep2.types import CurrencyCode
from httpx import AsyncClient
from sqlalchemy import func, select, update

from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


@pytest.mark.anyio
async def test_get_all_tariffs(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(TariffListUri, params={"limit": 3})
    assert resp.status_code == HTTPStatus.OK
    tariff_page = TariffPageResponse(**json.loads(resp.content))
    assert len(tariff_page.tariffs) == 3
    assert tariff_page.limit == 3
    assert tariff_page.start == 0
    assert tariff_page.group is None
    assert tariff_page.total_count == 3


@pytest.mark.parametrize(
    "group, expected_tariff_ids",
    [
        (None, [3, 2, 1]),
        ("Group-1", [3, 1]),  # tariff 1 scoped to Group-1, tariff 3 globally visible
        ("Group-2", [3, 2]),  # tariff 2 scoped to Group-2, tariff 3 globally visible
        ("Group-3", [3]),  # only the globally visible tariff
        ("Group-DNE", [3]),  # only the globally visible tariff
    ],
)
@pytest.mark.anyio
async def test_get_all_tariffs_group_filter(
    admin_client_auth: AsyncClient, pg_base_config, group: str | None, expected_tariff_ids: list[int]
):
    """Sanity check that the "group" query param filters tariffs against their required_site_group (or null)"""
    async with generate_async_session(pg_base_config) as session:
        await session.execute(update(Tariff).where(Tariff.tariff_id == 1).values(required_site_group_id=1))
        await session.execute(update(Tariff).where(Tariff.tariff_id == 2).values(required_site_group_id=2))
        await session.commit()

    params = {} if group is None else {"group": group}
    resp = await admin_client_auth.get(TariffListUri, params=params)
    assert resp.status_code == HTTPStatus.OK
    tariff_page = TariffPageResponse(**json.loads(resp.content))

    assert tariff_page.group == group
    assert tariff_page.total_count == len(expected_tariff_ids)
    assert expected_tariff_ids == [t.tariff_id for t in tariff_page.tariffs]


@pytest.mark.anyio
async def test_get_single_tariff(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(TariffUpdateUri.format(tariff_id=1))
    assert resp.status_code == HTTPStatus.OK
    tariff_resp = TariffResponse(**json.loads(resp.content))
    assert tariff_resp.tariff_id == 1


@pytest.mark.anyio
async def test_create_tariff(admin_client_auth: AsyncClient):
    tariff = generate_class_instance(TariffRequest, required_site_group_id=None)
    tariff.currency_code = CurrencyCode.AUSTRALIAN_DOLLAR
    resp = await admin_client_auth.post(TariffListUri, json=tariff.model_dump())

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.anyio
async def test_update_tariff(admin_client_auth: AsyncClient):
    tariff = generate_class_instance(TariffRequest, required_site_group_id=None)
    tariff.currency_code = CurrencyCode.AUSTRALIAN_DOLLAR
    resp = await admin_client_auth.put(TariffUpdateUri.format(tariff_id=1), json=tariff.model_dump())

    assert resp.status_code == HTTPStatus.OK


@pytest.mark.anyio
async def test_create_tariff_genrates(admin_client_auth: AsyncClient):
    tariff_genrate = generate_class_instance(TariffGeneratedRateRequest, tariff_id=1, site_group_id=1)

    tariff_genrate_1 = generate_class_instance(TariffGeneratedRateRequest, tariff_id=2, site_group_id=2)

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
        site_group_id=2,
        start_time=datetime(2022, 3, 5, 1, 2, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=1113,
        calculation_log_id=3,
        import_active_price=Decimal(1),
        export_active_price=Decimal(2),
        import_reactive_price=Decimal(3),
        export_reactive_price=Decimal(4),
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
        assert_nowish(db_rate.created_time)  # Updated record was archived. This is a newly inserted record
        assert db_rate.import_active_price == updated_rate.import_active_price
        assert db_rate.export_active_price == updated_rate.export_active_price
        assert db_rate.import_reactive_price == updated_rate.import_reactive_price
        assert db_rate.export_reactive_price == updated_rate.export_reactive_price

        assert (
            await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))
        ).scalar_one() == 1, "The old updated record should be archived. Unit tests will test this in more detail"
