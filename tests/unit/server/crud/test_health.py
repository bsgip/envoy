import unittest.mock as mock
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from envoy.server.crud.health import (
    DynamicOperatingEnvelopeCheck,
    DynamicPriceCheck,
    HealthCheck,
    check_database,
    check_dynamic_operating_envelopes,
    check_dynamic_prices,
)
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate
from tests.postgres_testing import generate_async_session


def test_health_defaults():
    check = HealthCheck()
    assert not check.database_connectivity
    assert not check.database_has_data


@pytest.mark.anyio
async def test_health_check_ok(pg_base_config):
    """Tests that the health check returns OK on the basic database config"""
    async with generate_async_session(pg_base_config) as session:
        check = HealthCheck()
        await check_database(session, check)
        assert check.database_connectivity
        assert check.database_has_data


@pytest.mark.anyio
async def test_health_check_no_data(pg_empty_config):
    """Tests that the health check returns failure on the empty DB"""
    async with generate_async_session(pg_empty_config) as session:
        check = HealthCheck()
        await check_database(session, check)
        assert check.database_connectivity
        assert not check.database_has_data


@pytest.mark.anyio
async def test_health_check_bad_db():
    """Tests that causing the db checks to raise an exception correctly populates the check"""
    check = HealthCheck()
    session = mock.Mock()
    session.execute = mock.Mock(side_effect=Exception("my mock error"))
    await check_database(session, check)
    assert not check.database_connectivity
    assert not check.database_has_data
    session.execute.assert_called_once()


@pytest.mark.anyio
async def test_health_doe_check_no_data(pg_empty_config):
    """Tests that the doe health check returns failure on the empty DB"""
    async with generate_async_session(pg_empty_config) as session:
        check = DynamicOperatingEnvelopeCheck()
        await check_dynamic_operating_envelopes(session, check)
        assert not check.has_does
        assert not check.has_future_does


@pytest.mark.anyio
async def test_health_doe_check_no_future_does(pg_base_config):
    """Tests that the doe health check returns failure if there are no future DOEs"""
    async with generate_async_session(pg_base_config) as session:
        check = DynamicOperatingEnvelopeCheck()
        await check_dynamic_operating_envelopes(session, check)
        assert check.has_does
        assert not check.has_future_does


@pytest.mark.anyio
async def test_health_doe_check_with_future_does(pg_base_config):
    """Tests that the doe health check returns failure if there are no future DOEs"""

    # Update start time so we have a future DOE
    now = datetime.now(tz=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        stmt = select(DynamicOperatingEnvelope).where(DynamicOperatingEnvelope.dynamic_operating_envelope_id == 3)
        resp = await session.execute(stmt)
        doe: DynamicOperatingEnvelope = resp.scalar_one()
        doe.start_time = now + timedelta(seconds=100)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        check = DynamicOperatingEnvelopeCheck()
        await check_dynamic_operating_envelopes(session, check)
        assert check.has_does
        assert check.has_future_does


@pytest.mark.anyio
async def test_health_price_check_no_data(pg_empty_config):
    """Tests that the price health check returns failure on the empty DB"""
    async with generate_async_session(pg_empty_config) as session:
        check = DynamicPriceCheck()
        await check_dynamic_prices(session, check)
        assert not check.has_dynamic_prices
        assert not check.has_future_prices


@pytest.mark.anyio
async def test_health_price_check_no_future_prices(pg_base_config):
    """Tests that the price health check returns failure if there are no future prices"""
    async with generate_async_session(pg_base_config) as session:
        check = DynamicPriceCheck()
        await check_dynamic_prices(session, check)
        assert check.has_dynamic_prices
        assert not check.has_future_prices


@pytest.mark.anyio
async def test_health_price_check_with_future_prices(pg_base_config):
    """Tests that the price health check returns failure if there are no future prices"""

    # Update start time so we have a future price
    now = datetime.now(tz=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        stmt = select(TariffGeneratedRate).where(TariffGeneratedRate.tariff_generated_rate_id == 4)
        resp = await session.execute(stmt)
        rate: TariffGeneratedRate = resp.scalar_one()
        rate.start_time = now + timedelta(seconds=101)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        check = DynamicPriceCheck()
        await check_dynamic_prices(session, check)
        assert check.has_dynamic_prices
        assert check.has_future_prices
