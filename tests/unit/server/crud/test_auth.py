import pytest

from server.crud.auth import select_client_ids_using_lfdi
from tests.test_db import generate_async_session

pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_select_client_ids_using_lfdi(pg_base_config):
    """Tests that select_client_ids_using_lfdi behaves with the base config"""
    with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        assert await select_client_ids_using_lfdi('active-lfdi-agg1-1', session) == {
            "certificate_id": 1,
            "aggregator_id": 1,
        }

        assert await select_client_ids_using_lfdi('active-lfdi-agg1-2', session) == {
            "certificate_id": 2,
            "aggregator_id": 1,
        }

        # This is an expired cert
        assert await select_client_ids_using_lfdi('expired-lfdi-agg1-1', session) is None

        assert await select_client_ids_using_lfdi('active-lfdi-agg2-1', session) == {
            "certificate_id": 4,
            "aggregator_id": 2,
        }

        # Test bad LFDIs
        assert await select_client_ids_using_lfdi('', session) is None
        assert await select_client_ids_using_lfdi('active-lfdi', session) is None
        assert await select_client_ids_using_lfdi('\' --', session) is None
