import pytest
import psycopg

from assertical.fixtures import postgres as pg_fixtures
from envoy.admin.crud import certificate as cert_crud
from envoy.server.model import base as base_model


@pytest.mark.anyio
async def test_count_certificates_for_aggregator(pg_base_config: psycopg.Connection) -> None:
    async with pg_fixtures.generate_async_session(pg_base_config) as session:
        assert (await cert_crud.count_certificates_for_aggregator(session, aggregator_id=1)) == 3


@pytest.mark.parametrize(
    "agg_id,expected_certs",
    [
        (1, [1, 2, 3]),
        (2, [4]),
        (3, [5]),
    ],
)
@pytest.mark.anyio
async def test_select_all_certificates_for_aggregator(
    pg_base_config: psycopg.Connection, agg_id: int, expected_certs: list[int]
) -> None:
    async with pg_fixtures.generate_async_session(pg_base_config) as session:
        certs = await cert_crud.select_all_certificates_for_aggregator(session, agg_id, 0, 100)
        assert all([isinstance(c, base_model.Certificate) for c in certs])
        assert expected_certs == [c.certificate_id for c in certs]
