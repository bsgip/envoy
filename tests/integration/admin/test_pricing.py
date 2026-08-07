import json
from datetime import UTC, datetime
from http import HTTPStatus
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.base import BatchCreateCollidableResponse, BatchCreateResponse, OnCollide
from envoy_schema.admin.schema.pricing import (
    TariffComponentRequest,
    TariffComponentResponse,
    TariffGeneratedRatePageResponse,
    TariffGeneratedRateRequest,
    TariffGeneratedRateResponse,
    TariffPageResponse,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.admin.schema.uri import (
    TariffComponentCreateUri,
    TariffComponentListUri,
    TariffComponentUpdateUri,
    TariffGeneratedRateCreateUri,
    TariffGeneratedRateListUri,
    TariffGeneratedRateUpdateUri,
    TariffListUri,
    TariffUpdateUri,
)
from envoy_schema.server.schema.sep2.types import CurrencyCode
from httpx import AsyncClient
from sqlalchemy import func, select, update

from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffComponent, ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate
from tests.integration.response import read_response_body_string


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
async def test_create_tariff_with_fetch(admin_client_auth: AsyncClient):
    """Can we create a Tariff and then refetch the thing we just created"""
    tariff = generate_class_instance(TariffRequest, required_site_group_id=None)
    tariff.currency_code = CurrencyCode.AUSTRALIAN_DOLLAR
    resp = await admin_client_auth.post(TariffListUri, json=tariff.model_dump())

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
        (1, generate_class_instance(TariffRequest, required_site_group_id=3), HTTPStatus.NO_CONTENT),
        (1, generate_class_instance(TariffRequest, required_site_group_id=99), HTTPStatus.BAD_REQUEST),  # fk mismatch
        (
            3,
            generate_class_instance(TariffRequest, required_site_group_id=4, optional_is_none=True),
            HTTPStatus.NO_CONTENT,
        ),
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
    original_tc: TariffComponentResponse | None = None
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
        TariffGeneratedRateRequest, seed=101, tariff_component_id=1, site_group_id=2, calculation_log_id=1
    )

    tariff_genrate_2 = generate_class_instance(
        TariffGeneratedRateRequest, seed=202, tariff_component_id=2, site_group_id=4, calculation_log_id=None
    )

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{tariff_genrate_1.model_dump_json()}, {tariff_genrate_2.model_dump_json()}]",
    )

    assert resp.status_code == HTTPStatus.CREATED
    rate_resp = BatchCreateResponse(**json.loads(resp.content))

    assert rate_resp.ids == [8, 9], "We know that the DB sequence is set to 8 in base_config.sql"

    for new_id, expected_genrate in zip(rate_resp.ids, [tariff_genrate_1, tariff_genrate_2], strict=False):
        # Now refetch each newly created record
        resp = await admin_client_auth.get(TariffGeneratedRateUpdateUri.format(tariff_generated_rate_id=new_id))
        assert resp.status_code == HTTPStatus.OK
        actual_genrate = TariffGeneratedRateResponse(**json.loads(resp.content))

        assert_class_instance_equality(TariffGeneratedRateRequest, expected_genrate, actual_genrate)
        assert actual_genrate.tariff_generated_rate_id == new_id
        assert_nowish(actual_genrate.created_time)
        assert_nowish(actual_genrate.changed_time)


@pytest.mark.anyio
async def test_create_tariff_genrates_on_collide_error_default(pg_base_config, admin_client_auth: AsyncClient):
    """The default (and explicit "error") on_collide behaviour should reject the entire batch (writing nothing) if
    any entity collides with an existing record on (tariff_component_id, start_time, site_group_id)"""

    async with generate_async_session(pg_base_config) as session:
        before_count = (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one()

    # Collides with tariff_generated_rate_id 1 (tariff_component_id=1, site_group_id=2, start_time=2022-03-05 01:00+10)
    colliding_rate = TariffGeneratedRateRequest(
        tariff_component_id=1,
        site_group_id=2,
        start_time=datetime(2022, 3, 5, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=11,
        calculation_log_id=None,
        price_pow10_encoded=999999,
    )
    new_rate = generate_class_instance(
        TariffGeneratedRateRequest, seed=303, tariff_component_id=2, site_group_id=2, calculation_log_id=None
    )

    for query_params in [{}, {"on_collide": str(OnCollide.error)}]:
        resp = await admin_client_auth.post(
            TariffGeneratedRateCreateUri,
            content=f"[{colliding_rate.model_dump_json()}, {new_rate.model_dump_json()}]",
            headers={"Content-Type": "application/json"},
            params=query_params,
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    # Nothing should have been written
    async with generate_async_session(pg_base_config) as session:
        after_count = (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one()
        archive_count = (
            await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))
        ).scalar_one()
        assert after_count == before_count
        assert archive_count == 0


@pytest.mark.anyio
async def test_create_tariff_genrates_on_collide_ignore(pg_base_config, admin_client_auth: AsyncClient):
    """on_collide=ignore should skip (not insert) colliding entities but preserve 1-1 correspondence with -1"""

    async with generate_async_session(pg_base_config) as session:
        before_count = (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one()

    # Collides with tariff_generated_rate_id 1
    colliding_rate = TariffGeneratedRateRequest(
        tariff_component_id=1,
        site_group_id=2,
        start_time=datetime(2022, 3, 5, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=11,
        calculation_log_id=None,
        price_pow10_encoded=999999,
    )
    new_rate = generate_class_instance(
        TariffGeneratedRateRequest, seed=303, tariff_component_id=2, site_group_id=2, calculation_log_id=None
    )

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{colliding_rate.model_dump_json()}, {new_rate.model_dump_json()}]",
        headers={"Content-Type": "application/json"},
        params={"on_collide": OnCollide.ignore},
    )
    assert resp.status_code == HTTPStatus.CREATED
    rate_resp = BatchCreateCollidableResponse(**json.loads(resp.content))

    assert rate_resp.on_collide == OnCollide.ignore
    assert len(rate_resp.ids) == 2
    assert rate_resp.ids[0] is None, "This entity collided and should've been skipped"
    assert isinstance(rate_resp.ids[1], int)

    async with generate_async_session(pg_base_config) as session:
        after_count = (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one()
        archive_count = (
            await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))
        ).scalar_one()
        assert after_count == before_count + 1, "Only the non-colliding entity should've been inserted"
        assert archive_count == 0, "Nothing should be cancelled/archived in ignore mode"

        # The original colliding record should remain completely untouched
        original_rate = (
            await session.execute(select(TariffGeneratedRate).where(TariffGeneratedRate.tariff_generated_rate_id == 1))
        ).scalar_one()
        assert original_rate.price_pow10_encoded == 1111

        new_rate_db = (
            await session.execute(
                select(TariffGeneratedRate).where(TariffGeneratedRate.tariff_generated_rate_id == rate_resp.ids[1])
            )
        ).scalar_one()
        assert new_rate_db.tariff_component_id == new_rate.tariff_component_id
        assert new_rate_db.site_group_id == new_rate.site_group_id


@pytest.mark.anyio
async def test_create_tariff_genrates_on_collide_cancel(pg_base_config, admin_client_auth: AsyncClient):
    """on_collide=cancel should cancel (archive/delete) any existing colliding entities before inserting"""

    async with generate_async_session(pg_base_config) as session:
        before_count = (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one()

    # Collides with tariff_generated_rate_id 1
    colliding_rate = TariffGeneratedRateRequest(
        tariff_component_id=1,
        site_group_id=2,
        start_time=datetime(2022, 3, 5, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=11,
        calculation_log_id=None,
        price_pow10_encoded=999999,
    )
    new_rate = generate_class_instance(
        TariffGeneratedRateRequest, seed=303, tariff_component_id=2, site_group_id=2, calculation_log_id=None
    )

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{colliding_rate.model_dump_json()}, {new_rate.model_dump_json()}]",
        headers={"Content-Type": "application/json"},
        params={"on_collide": OnCollide.cancel},
    )
    assert resp.status_code == HTTPStatus.CREATED
    rate_resp = BatchCreateCollidableResponse(**json.loads(resp.content))

    assert rate_resp.on_collide == OnCollide.cancel
    assert len(rate_resp.ids) == 2
    assert all(i != -1 for i in rate_resp.ids), "Both entities should've been inserted with fresh ids"
    assert 1 not in rate_resp.ids, "The old (cancelled) id should not be reused"

    async with generate_async_session(pg_base_config) as session:
        after_count = (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one()
        assert after_count == before_count + 1, "1 cancelled + 2 inserted = net +1"

        # Old record 1 should be gone from the live table and archived (as a delete/cancellation)
        old_record = (
            await session.execute(
                select(func.count())
                .select_from(TariffGeneratedRate)
                .where(TariffGeneratedRate.tariff_generated_rate_id == 1)
            )
        ).scalar_one()
        assert old_record == 0

        archived = (
            await session.execute(
                select(ArchiveTariffGeneratedRate).where(ArchiveTariffGeneratedRate.tariff_generated_rate_id == 1)
            )
        ).scalar_one()
        assert archived.deleted_time is not None
        assert archived.price_pow10_encoded == 1111, "The archived record should reflect the OLD price"

        # The replacement record should have the new price at the same natural key
        replacement = (
            await session.execute(
                select(TariffGeneratedRate)
                .where(TariffGeneratedRate.tariff_component_id == 1)
                .where(TariffGeneratedRate.site_group_id == 2)
                .where(TariffGeneratedRate.start_time == colliding_rate.start_time)
            )
        ).scalar_one()
        assert replacement.price_pow10_encoded == 999999
        assert replacement.tariff_generated_rate_id in rate_resp.ids


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


@pytest.mark.parametrize(
    "tariff_generated_rate_id, expected_status",
    [(1, HTTPStatus.NO_CONTENT), (4, HTTPStatus.NO_CONTENT), (99, HTTPStatus.NO_CONTENT)],
)
@pytest.mark.anyio
async def test_delete_tariff_generated_rate(
    pg_base_config, admin_client_auth: AsyncClient, tariff_generated_rate_id: int, expected_status: HTTPStatus
):
    async with generate_async_session(pg_base_config) as session:
        stmt = (
            select(func.count())
            .select_from(TariffGeneratedRate)
            .where(TariffGeneratedRate.tariff_generated_rate_id == tariff_generated_rate_id)
        )
        resp = await session.execute(stmt)
        exists = (resp.scalar_one()) == 1

    resp = await admin_client_auth.delete(
        TariffGeneratedRateUpdateUri.format(tariff_generated_rate_id=tariff_generated_rate_id)
    )
    assert resp.status_code == expected_status

    async with generate_async_session(pg_base_config) as session:
        after_count = (
            await session.execute(
                select(func.count())
                .select_from(TariffGeneratedRate)
                .where(TariffGeneratedRate.tariff_generated_rate_id == tariff_generated_rate_id)
            )
        ).scalar_one()
        archive_count = (
            await session.execute(
                select(func.count())
                .select_from(ArchiveTariffGeneratedRate)
                .where(ArchiveTariffGeneratedRate.tariff_generated_rate_id == tariff_generated_rate_id)
                .where(ArchiveTariffGeneratedRate.deleted_time.is_not(None))
            )
        ).scalar_one()

        if exists:
            assert after_count == 0
            assert archive_count == 1
        else:
            assert after_count == 0
            assert archive_count == 0


@pytest.mark.parametrize(
    "tariff_component_id, expected_status",
    [(1, HTTPStatus.NO_CONTENT), (4, HTTPStatus.NO_CONTENT), (99, HTTPStatus.NO_CONTENT)],
)
@pytest.mark.anyio
async def test_delete_tariff_component(
    pg_base_config, admin_client_auth: AsyncClient, tariff_component_id: int, expected_status: HTTPStatus
):
    async with generate_async_session(pg_base_config) as session:
        stmt = (
            select(func.count())
            .select_from(TariffComponent)
            .where(TariffComponent.tariff_component_id == tariff_component_id)
        )
        resp = await session.execute(stmt)
        exists = (resp.scalar_one()) == 1

    resp = await admin_client_auth.delete(TariffComponentUpdateUri.format(tariff_component_id=tariff_component_id))
    assert resp.status_code == expected_status

    async with generate_async_session(pg_base_config) as session:
        after_count = (
            await session.execute(
                select(func.count())
                .select_from(TariffComponent)
                .where(TariffComponent.tariff_component_id == tariff_component_id)
            )
        ).scalar_one()
        archive_count = (
            await session.execute(
                select(func.count())
                .select_from(ArchiveTariffComponent)
                .where(ArchiveTariffComponent.tariff_component_id == tariff_component_id)
                .where(ArchiveTariffComponent.deleted_time.is_not(None))
            )
        ).scalar_one()

        if exists:
            assert after_count == 0
            assert archive_count == 1
        else:
            assert after_count == 0
            assert archive_count == 0


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
        site_group_id=2,
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


@pytest.mark.parametrize(
    "tariff_id, expected_status, expected_component_ids",
    [
        (1, HTTPStatus.OK, [1, 2, 3]),  # Tariff 1 owns TC 1, 2, 3
        (2, HTTPStatus.OK, [4]),  # Tariff 2 owns TC 4
        (3, HTTPStatus.OK, []),  # Tariff 3 has no components
        (99, HTTPStatus.NOT_FOUND, None),  # Unknown tariff
    ],
)
@pytest.mark.anyio
async def test_get_tariff_components_for_tariff(
    admin_client_auth: AsyncClient,
    tariff_id: int,
    expected_status: HTTPStatus,
    expected_component_ids: list[int] | None,
):
    """Test GET /tariff/{tariff_id}/tariff_component returns all components ordered by id."""
    resp = await admin_client_auth.get(TariffComponentListUri.format(tariff_id=tariff_id))
    assert resp.status_code == expected_status

    if expected_status == HTTPStatus.OK:
        assert expected_component_ids is not None
        components = [TariffComponentResponse(**c) for c in json.loads(read_response_body_string(resp))]
        assert [c.tariff_component_id for c in components] == expected_component_ids
        for c in components:
            assert c.tariff_id == tariff_id


def build_rate_params(
    start_time_since: datetime | None,
    start_time_until: datetime | None,
    group: str | None,
    start: int | None,
    limit: int | None,
    site_id: int | None,
) -> str:
    """Builds up a paging query string in the form of ?start={start}&limit={limit} etc."""

    parts: list[str] = []
    if start is not None:
        parts.append(f"start={start}")
    if limit is not None:
        parts.append(f"limit={limit}")
    if start_time_since is not None:
        parts.append(f"start_time_since={quote_plus(start_time_since.isoformat())}")
    if start_time_until is not None:
        parts.append(f"start_time_until={quote_plus(start_time_until.isoformat())}")
    if group is not None:
        parts.append(f"group={quote_plus(group)}")
    if site_id is not None:
        parts.append(f"site_id={site_id}")

    return "?" + "&".join(parts)


@pytest.mark.parametrize(
    "tariff_component_id,start_time_since,start_time_until,group,site_id,start,limit,expected_ids,expected_count",
    [
        (99, None, None, None, None, None, 100, [], 0),  # basic filter
        (1, None, None, None, None, None, 100, [1, 2, 3, 4, 5], 5),  # basic filter
        (1, None, None, None, None, 1, 2, [2, 3], 5),  # paging
        (2, None, None, None, None, None, 100, [6], 1),
        (3, None, None, None, None, None, 100, [], 0),
        (1, None, None, None, 99, None, 100, [], 0),  # site DNE
        (1, None, None, None, 1, None, 100, [1, 2, 3], 3),
        (1, None, None, "Group-2", None, None, 100, [1, 2, 3], 3),
        (1, None, None, "Group-DNE", None, None, 100, [], 0),
        (1, datetime(2000, 1, 1, tzinfo=UTC), datetime(2001, 1, 1, tzinfo=UTC), None, None, None, 100, [], 0),
        (
            1,
            datetime(2000, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, tzinfo=UTC),
            None,
            None,
            None,
            100,
            [1, 2, 3, 4, 5],
            5,
        ),
        (
            1,
            datetime(2022, 3, 4, 15, 0, 11, tzinfo=UTC),
            None,
            None,
            None,
            0,
            100,
            [2, 3],
            2,
        ),
        (
            1,
            datetime(2022, 3, 4, 15, 0, 0, tzinfo=UTC),
            datetime(2022, 3, 4, 15, 0, 33, tzinfo=UTC),
            "Group-2",
            1,
            0,
            100,
            [1, 2],
            2,
        ),
    ],
)
@pytest.mark.anyio
async def test_get_tariff_generated_rates_filtered(
    admin_client_auth: AsyncClient,
    tariff_component_id: int,
    start_time_since: datetime | None,
    start_time_until: datetime | None,
    group: str | None,
    start: int | None,
    limit: int | None,
    site_id: int | None,
    expected_ids: list[int],
    expected_count: int,
):
    """Tests fetching and filtering tariff rates"""
    url = TariffGeneratedRateListUri.format(tariff_component_id=tariff_component_id) + build_rate_params(
        start_time_since=start_time_since,
        start_time_until=start_time_until,
        start=start,
        limit=limit,
        site_id=site_id,
        group=group,
    )
    resp = await admin_client_auth.get(url)
    assert resp.status_code == HTTPStatus.OK

    response_page = TariffGeneratedRatePageResponse(**json.loads(resp.content))

    assert response_page.group == group
    assert response_page.start_time_since == start_time_since
    assert response_page.start_time_until == start_time_until
    assert response_page.site_id == site_id
    assert response_page.tariff_component_id == tariff_component_id

    if limit is None:
        assert isinstance(response_page.limit, int) and response_page.limit > 0
    else:
        assert response_page.limit == limit

    if start is None:
        assert isinstance(response_page.start, int) and response_page.start == 0
    else:
        assert response_page.start == start

    assert response_page.total_count == expected_count
    assert_list_type(TariffGeneratedRateResponse, response_page.rates, count=len(expected_ids))
    assert expected_ids == [r.tariff_generated_rate_id for r in response_page.rates]
