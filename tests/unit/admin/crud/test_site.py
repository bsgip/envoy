from typing import Optional

import pytest
from sqlalchemy.exc import InvalidRequestError

from envoy.admin.crud.site import count_all_site_groups, count_all_sites, select_all_site_groups, select_all_sites
from envoy.server.model.site import Site, SiteGroup
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_count_all_sites(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_sites(session, None)) == 4
        assert (await count_all_sites(session, "")) == 4
        assert (await count_all_sites(session, "Group-1")) == 3
        assert (await count_all_sites(session, "Group-2")) == 1
        assert (await count_all_sites(session, "Group-3")) == 0
        assert (await count_all_sites(session, "Group DNE")) == 0


@pytest.mark.anyio
async def test_count_all_sites_empty(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        assert (await count_all_sites(session, None)) == 0
        assert (await count_all_sites(session, "Group-1")) == 0


@pytest.mark.parametrize(
    "start, limit, group, expected_site_ids, expected_group_ids",
    [
        (0, 500, None, [1, 2, 3, 4], [[1, 2], [1], [1], []]),
        (0, 500, "", [1, 2, 3, 4], [[1, 2], [1], [1], []]),
        (0, 500, "Group-1", [1, 2, 3], [[1, 2], [1], [1]]),
        (0, 500, "Group-2", [1], [[1, 2]]),
        (0, 500, "Group-3", [], []),
        (0, 500, "Group-DNE", [], []),
        (1, 500, None, [2, 3, 4], [[1], [1], []]),
        (2, 500, None, [3, 4], [[1], []]),
        (3, 500, None, [4], [[]]),
        (4, 500, None, [], []),
        (1, 2, None, [2, 3], [[1], [1]]),
        (2, 2, None, [3, 4], [[1], []]),
        (0, 0, None, [], []),
        (1, 1, "Group-1", [2], [[1]]),
    ],
)
@pytest.mark.anyio
async def test_select_all_sites(
    pg_base_config,
    start: int,
    limit: int,
    group: Optional[str],
    expected_site_ids: list[int],
    expected_group_ids: list[list[int]],
):
    async with generate_async_session(pg_base_config) as session:
        sites_no_groups = await select_all_sites(session, group, start, limit, include_groups=False)

    async with generate_async_session(pg_base_config) as session:
        sites_with_groups = await select_all_sites(session, group, start, limit, include_groups=True)

    # Validate groups vs no groups are identical
    assert all([isinstance(s, Site) for s in sites_no_groups])
    assert all([isinstance(s, Site) for s in sites_with_groups])
    assert len(sites_no_groups) == len(sites_with_groups)
    assert expected_site_ids == [s.site_id for s in sites_no_groups]
    assert expected_site_ids == [s.site_id for s in sites_with_groups]

    # Validate the groups were returned as expected
    assert expected_group_ids == [[a.group.site_group_id for a in s.assignments] for s in sites_with_groups]

    # And that sites without groups don't have any groups
    if len(sites_no_groups) > 0:
        with pytest.raises(InvalidRequestError):
            assert all([len(s.assignments) == 0 for s in sites_no_groups])


@pytest.mark.anyio
async def test_count_all_site_groups(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_site_groups(session)) == 3


@pytest.mark.anyio
async def test_count_all_site_groups_empty(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        assert (await count_all_site_groups(session)) == 0


@pytest.mark.parametrize(
    "start, limit, group, expected_id_count",
    [
        (0, 500, None, [(1, 3), (2, 1), (3, 0)]),
        (0, 2, None, [(1, 3), (2, 1)]),
        (1, 2, None, [(2, 1), (3, 0)]),
        (2, 2, None, [(3, 0)]),
        (0, 500, "Group-1", [(1, 3)]),
        (0, 500, "Group-2", [(2, 1)]),
        (0, 500, "Group-3", [(3, 0)]),
        (0, 500, "Group-DNE", []),
    ],
)
@pytest.mark.anyio
async def test_select_all_site_groups(
    pg_base_config, start: int, limit: int, group: Optional[str], expected_id_count: list[tuple[int, int]]
):
    """Selects groups with their counts and makes sure everything lines up"""
    async with generate_async_session(pg_base_config) as session:
        groups = await select_all_site_groups(session, group, start, limit)
        assert len(groups) == len(expected_id_count)

        assert all([isinstance(g, tuple) for g in groups])
        assert all([isinstance(g[0], SiteGroup) for g in groups])
        assert all([isinstance(g[1], int) for g in groups])
        assert expected_id_count == [(sg.site_group_id, count) for sg, count in groups]
