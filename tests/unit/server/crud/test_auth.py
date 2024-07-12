import pytest
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session

from envoy.server.crud.auth import ClientIdDetails, select_all_client_id_details


@pytest.mark.anyio
async def test_select_all_client_id_details(pg_base_config):
    """Tests that select_all_client_id_details behaves with the base config.
    Base config has 4 active certificates registered."""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        result = await select_all_client_id_details(session)

    assert_list_type(ClientIdDetails, result, count=4)
