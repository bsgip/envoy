import pytest

from envoy.admin.crud.site import count_all_sites, select_all_sites
from envoy.server.model.site import Site
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_count_all_sites(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_sites(session)) == 4


@pytest.mark.anyio
async def test_count_all_sites_empty(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        assert (await count_all_sites(session)) == 0


@pytest.mark.parametrize(
    "start, limit, expected_site_ids",
    [
        (0, 500, [1, 2, 3, 4]),
        (1, 500, [2, 3, 4]),
        (2, 500, [3, 4]),
        (3, 500, [4]),
        (4, 500, []),
        (1, 2, [2, 3]),
        (2, 2, [3, 4]),
        (0, 0, []),
    ],
)
@pytest.mark.anyio
async def test_select_all_sites(pg_base_config, start: int, limit: int, expected_site_ids: list[int]):
    async with generate_async_session(pg_base_config) as session:
        sites = await select_all_sites(session, start, limit)
        assert len(sites) == len(expected_site_ids)
        assert all([isinstance(s, Site) for s in sites])
        assert expected_site_ids == [s.site_id for s in sites]
