import pytest

from envoy.server.crud.auth import ClientIdDetails, select_all_client_id_details
from tests.postgres_testing import generate_async_session
from tests.assert_type import assert_list_type


@pytest.mark.anyio
async def test_select_all_client_id_details(pg_base_config):
    """Tests that select_all_client_id_details behaves with the base config"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        result = await select_all_client_id_details(session)

    print(result)
    assert_list_type(ClientIdDetails, result, count=4)
