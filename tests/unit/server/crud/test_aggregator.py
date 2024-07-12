import pytest
from assertical.fixtures.postgres import generate_async_session

from envoy.server.crud.aggregator import select_aggregator
from envoy.server.model.aggregator import Aggregator


@pytest.mark.anyio
async def test_select_aggregator(pg_base_config):
    async with generate_async_session(pg_base_config) as session:

        agg_1 = await select_aggregator(session, 1)
        assert isinstance(agg_1, Aggregator)
        assert len(agg_1.domains) == 2
        assert [d.domain for d in agg_1.domains] == ["example.com", "another.example.com"]
        assert agg_1.name == "Aggregator 1"

        agg_2 = await select_aggregator(session, 2)
        assert isinstance(agg_2, Aggregator)
        assert len(agg_2.domains) == 1
        assert [d.domain for d in agg_2.domains] == ["example.com"]
        assert agg_2.name == "Aggregator 2"

        assert (await select_aggregator(session, 4)) is None
        assert (await select_aggregator(session, -1)) is None
