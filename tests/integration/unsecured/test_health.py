from datetime import datetime, timedelta, timezone
from http import HTTPStatus

import pytest
from assertical.fixtures.postgres import generate_async_session
from httpx import AsyncClient
from sqlalchemy import select

from envoy.server.api.unsecured.health import HEALTH_DOE_URI, HEALTH_DYNAMIC_PRICE_URI, HEALTH_URI
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate
from tests.integration.response import read_response_body_string


@pytest.mark.anyio
async def test_get_health_works_for_any_auth(client: AsyncClient, valid_headers):
    """Checks HEALTH_URI returns HTTP 200 for all requests (ignoring auth)"""

    # no login
    response = await client.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"

    # valid login
    response = await client.request(method="GET", url=HEALTH_URI, headers=valid_headers)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_health_detects_no_data(client_empty_db: AsyncClient):
    """Checks the health check will fail if the DB is empty"""

    response = await client_empty_db.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_price_health_fails_no_future_prices(client: AsyncClient):
    """Checks HEALTH_DYNAMIC_PRICE_URI returns HTTP 500 if there are no future prices (the default for
    pg_base_config)"""

    response = await client.request(method="GET", url=HEALTH_DYNAMIC_PRICE_URI)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_price_health_works_for_any_auth(client: AsyncClient, pg_base_config, valid_headers):
    """Checks HEALTH_DYNAMIC_PRICE_URI returns HTTP 200 for all requests (ignoring auth)"""

    # Update start time so we have a future price
    now = datetime.now(tz=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        stmt = select(TariffGeneratedRate).where(TariffGeneratedRate.tariff_generated_rate_id == 4)
        resp = await session.execute(stmt)
        rate: TariffGeneratedRate = resp.scalar_one()
        rate.start_time = now + timedelta(seconds=102)
        await session.commit()

    # no login
    response = await client.request(method="GET", url=HEALTH_DYNAMIC_PRICE_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"

    # valid login
    response = await client.request(method="GET", url=HEALTH_DYNAMIC_PRICE_URI, headers=valid_headers)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_doe_health_fails_no_future_does(client: AsyncClient):
    """Checks HEALTH_DOE_URI returns HTTP 500 if there are no future does (the default for
    pg_base_config)"""

    response = await client.request(method="GET", url=HEALTH_DOE_URI)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_doe_health_works_for_any_auth(client: AsyncClient, pg_base_config, valid_headers):
    """Checks HEALTH_DOE_URI returns HTTP 200 for all requests (ignoring auth)"""

    # Update start time so we have a future price
    now = datetime.now(tz=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        stmt = select(DynamicOperatingEnvelope).where(DynamicOperatingEnvelope.dynamic_operating_envelope_id == 2)
        resp = await session.execute(stmt)
        doe: DynamicOperatingEnvelope = resp.scalar_one()
        doe.start_time = now + timedelta(seconds=103)
        await session.commit()

    # no login
    response = await client.request(method="GET", url=HEALTH_DOE_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"

    # valid login
    response = await client.request(method="GET", url=HEALTH_DOE_URI, headers=valid_headers)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"
