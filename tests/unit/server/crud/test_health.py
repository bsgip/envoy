import unittest.mock as mock

import pytest

from envoy.server.crud.health import HealthCheck, check_database
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
