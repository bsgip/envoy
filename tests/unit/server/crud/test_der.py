import pytest

from envoy.server.crud.der import select_site_der_for_site
from tests.postgres_testing import generate_async_session


@pytest.mark.parametrize("aggregator_id, site_id", [(2, 1), (1, 99), (99, 1)])
@pytest.mark.anyio
async def test_select_site_der_for_site_invalid_lookup(pg_base_config, aggregator_id: int, site_id: int):
    """Tests the various ways DER lookup can fail"""

    async with generate_async_session(pg_base_config) as session:
        assert await select_site_der_for_site(session, aggregator_id, site_id) is None
