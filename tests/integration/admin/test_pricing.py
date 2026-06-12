import json
from datetime import UTC, datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.base import BatchCreateResponse
from envoy_schema.admin.schema.pricing import (
    TariffComponentRequest,
    TariffComponentResponse,
    TariffGeneratedRatePageResponse,
    TariffGeneratedRateRequest,
    TariffGeneratedRateResponse,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.admin.schema.uri import (
    TariffComponentCreateUri,
    TariffComponentListUri,
    TariffComponentUpdateUri,
    TariffCreateUri,
    TariffGeneratedRateCreateUri,
    TariffGeneratedRateRangeUri,
    TariffGeneratedRateUpdateUri,
    TariffUpdateUri,
)
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.server.api.request import MAX_LIMIT
from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffComponent, ArchiveTariffGeneratedRate
from envoy.server.model.tariff import TariffComponent, TariffGeneratedRate
from tests.integration.response import read_response_body_string


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

    for new_id, expected_genrate in zip(rate_resp.ids, [tariff_genrate_1, tariff_genrate_2], strict=False):
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


# --- Tests for GET /tariff/{tariff_id}/tariff_component ---


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


# --- Tests for GET /tariff_component/{tariff_component_id}/tariff_generated_rate/{period_start}/{period_end} ---

# Base config rates (all start on 2022-03-04 UTC = 2022-03-05 +10):
# Rate 1: TC=1, site=1, start=2022-03-04T15:00:00Z, duration=11s
# Rate 2: TC=1, site=1, start=2022-03-04T15:00:11Z, duration=22s
# Rate 3: TC=1, site=1, start=2022-03-04T15:00:33Z, duration=33s
# Rate 4: TC=1, site=2, start=2022-03-04T15:00:00Z, duration=44s
# Rate 5: TC=1, site=3, start=2022-03-04T15:00:00Z, duration=55s
# Rate 6: TC=2, site=1, start=2022-03-04T15:00:00Z, duration=66s
# Rate 7: TC=4, site=1, start=2022-03-04T15:00:00Z, duration=77s

# Period covering all rates
RATE_PERIOD_START = datetime(2022, 3, 4, 14, 0, 0, tzinfo=UTC)
RATE_PERIOD_END = datetime(2022, 3, 4, 16, 0, 0, tzinfo=UTC)

# Period with no rates
RATE_PERIOD_EMPTY_START = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
RATE_PERIOD_EMPTY_END = datetime(2020, 1, 2, 0, 0, 0, tzinfo=UTC)

# TC#1 rates ordered by (start_time ASC, site_id ASC):
# rate 1 (site=1, T15:00:00Z), rate 4 (site=2, T15:00:00Z), rate 5 (site=3, T15:00:00Z),
# rate 2 (site=1, T15:00:11Z), rate 3 (site=1, T15:00:33Z)
TC1_RATE_IDS_ORDERED = [1, 4, 5, 2, 3]


GET_RATE_TEST_CASES = [
    # (tariff_component_id, start, limit, period_start, period_end, site_id, expected_rate_ids, expected_total)
    (1, 0, 999, RATE_PERIOD_START, RATE_PERIOD_END, None, TC1_RATE_IDS_ORDERED, 5),  # TC#1 all rates
    (2, 0, 999, RATE_PERIOD_START, RATE_PERIOD_END, None, [6], 1),  # TC#2 single rate
    (4, 0, 999, RATE_PERIOD_START, RATE_PERIOD_END, None, [7], 1),  # TC#4 single rate
    (3, 0, 999, RATE_PERIOD_START, RATE_PERIOD_END, None, [], 0),  # TC#3 no rates
    (1, 0, 999, RATE_PERIOD_EMPTY_START, RATE_PERIOD_EMPTY_END, None, [], 0),  # Empty period
    (1, 0, 2, RATE_PERIOD_START, RATE_PERIOD_END, None, [1, 4], 5),  # Pagination: first page
    (1, 2, 2, RATE_PERIOD_START, RATE_PERIOD_END, None, [5, 2], 5),  # Pagination: second page
    (1, 999, 999, RATE_PERIOD_START, RATE_PERIOD_END, None, [], 5),  # Pagination: past end
    (1, 0, 999, RATE_PERIOD_START, RATE_PERIOD_END, 1, [1, 2, 3], 3),  # Site filter: site 1
    (1, 0, 999, RATE_PERIOD_START, RATE_PERIOD_END, 2, [4], 1),  # Site filter: site 2
    (1, 0, 999, RATE_PERIOD_START, RATE_PERIOD_END, 999, [], 0),  # Site filter: no match
]


@pytest.mark.parametrize(
    "tariff_component_id, start, limit, period_start, period_end, site_id, expected_rate_ids, expected_total",
    GET_RATE_TEST_CASES,
)
@pytest.mark.anyio
async def test_get_tariff_generated_rates_for_period(
    admin_client_auth: AsyncClient,
    pg_base_config,
    tariff_component_id: int,
    start: int,
    limit: int,
    period_start: datetime,
    period_end: datetime,
    site_id: int | None,
    expected_rate_ids: list[int],
    expected_total: int,
):
    """Test GET /tariff_component/{cid}/tariff_generated_rate/{period_start}/{period_end}"""

    url = TariffGeneratedRateRangeUri.format(
        tariff_component_id=tariff_component_id,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )
    params = f"?start={start}&limit={limit}"
    if site_id is not None:
        params += f"&site_id={site_id}"

    response = await admin_client_auth.get(url + params)
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    page = TariffGeneratedRatePageResponse(**json.loads(body))

    if limit >= MAX_LIMIT:
        assert page.limit == MAX_LIMIT
    else:
        assert page.limit == limit
    assert page.start == start
    assert page.tariff_component_id == tariff_component_id
    assert page.total_count == expected_total
    assert page.site_id == site_id
    assert_list_type(TariffGeneratedRateResponse, page.rates, len(expected_rate_ids))
    assert expected_rate_ids == [r.tariff_generated_rate_id for r in page.rates]


@pytest.mark.anyio
async def test_get_tariff_generated_rates_unknown_component(admin_client_auth: AsyncClient):
    """Unknown tariff_component_id returns 404."""
    url = TariffGeneratedRateRangeUri.format(
        tariff_component_id=99,
        period_start=RATE_PERIOD_START.isoformat(),
        period_end=RATE_PERIOD_END.isoformat(),
    )
    assert (await admin_client_auth.get(url)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.anyio
async def test_get_tariff_generated_rates_response_fields(admin_client_auth: AsyncClient, pg_base_config):
    """Verify response fields for a known rate match the base config data."""

    url = TariffGeneratedRateRangeUri.format(
        tariff_component_id=1,
        period_start=RATE_PERIOD_START.isoformat(),
        period_end=RATE_PERIOD_END.isoformat(),
    )
    response = await admin_client_auth.get(url + "?start=0&limit=1")
    assert response.status_code == HTTPStatus.OK

    page = TariffGeneratedRatePageResponse(**json.loads(read_response_body_string(response)))
    assert len(page.rates) == 1
    assert page.tariff_component_id == 1

    rate = page.rates[0]
    assert rate.tariff_generated_rate_id == 1
    assert rate.tariff_id == 1
    assert rate.tariff_component_id == 1
    assert rate.site_id == 1
    assert rate.calculation_log_id == 2
    assert rate.duration_seconds == 11
    assert rate.price_pow10_encoded == 1111
    assert rate.block_1_start_pow10_encoded == 1000
    assert rate.price_pow10_encoded_block_1 == 1001
