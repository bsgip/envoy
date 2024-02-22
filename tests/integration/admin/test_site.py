import json
from http import HTTPStatus
from typing import Optional

import pytest
from envoy_schema.admin.schema.site import SitePageResponse, SiteResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse
from envoy_schema.admin.schema.uri import SiteGroupListUri, SiteGroupUri, SiteUri
from httpx import AsyncClient

from envoy.admin.crud.site import count_all_site_groups, count_all_sites
from tests.integration.response import read_response_body_string
from tests.postgres_testing import generate_async_session


def _build_query_string(start: Optional[int], limit: Optional[int], group_filter: Optional[str]) -> str:
    query = "?"
    if start is not None:
        query = query + f"&start={start}"
    if limit is not None:
        query = query + f"&limit={limit}"
    if group_filter is not None:
        query = query + f"&group={group_filter}"
    return query


@pytest.mark.parametrize(
    "start, limit, group, expected_site_ids",
    [
        (None, None, None, [1, 2, 3, 4]),
        (None, None, "Group-1", [1, 2, 3]),
        (None, None, "Group-2", [1]),
        (None, None, "Group-3", []),
        (None, None, "Group-DNE", []),
        (0, 10, None, [1, 2, 3, 4]),
        (2, 10, None, [3, 4]),
        (None, 2, None, [1, 2]),
        (2, 2, None, [3, 4]),
        (3, 2, None, [4]),
        (1, 1, "Group-1", [2]),
    ],
)
@pytest.mark.anyio
async def test_get_all_sites(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    group: Optional[str],
    expected_site_ids: list[int],
):
    expected_total_sites: int
    async with generate_async_session(pg_base_config) as session:
        expected_total_sites = await count_all_sites(session, group)

    response = await admin_client_auth.get(SiteUri + _build_query_string(start, limit, group))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    site_page: SitePageResponse = SitePageResponse(**json.loads(body))

    assert isinstance(site_page.limit, int)
    assert isinstance(site_page.total_count, int)
    assert isinstance(site_page.start, int)
    assert len(site_page.sites) == len(expected_site_ids)
    assert all([isinstance(s, SiteResponse) for s in site_page.sites])

    assert (
        site_page.total_count == expected_total_sites
    ), f"There are only {expected_total_sites} sites available in the current config for group {group}"
    if limit is not None:
        assert site_page.limit == limit
    if start is not None:
        assert site_page.start == start

    assert [s.site_id for s in site_page.sites] == expected_site_ids


@pytest.mark.parametrize(
    "start, limit, expected_group_count",
    [
        (None, None, [(1, 3), (2, 1), (3, 0)]),
        (None, 10, [(1, 3), (2, 1), (3, 0)]),
        (None, 2, [(1, 3), (2, 1)]),
        (1, 2, [(2, 1), (3, 0)]),
        (2, 2, [(3, 0)]),
        (3, 2, []),
        (3, None, []),
    ],
)
@pytest.mark.anyio
async def test_get_all_site_groups(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    expected_group_count: list[tuple[int, int]],
):
    expected_total_groups: int
    async with generate_async_session(pg_base_config) as session:
        expected_total_groups = await count_all_site_groups(session)

    response = await admin_client_auth.get(SiteGroupListUri + _build_query_string(start, limit, None))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    group_page: SiteGroupPageResponse = SiteGroupPageResponse(**json.loads(body))

    assert isinstance(group_page.limit, int)
    assert isinstance(group_page.total_count, int)
    assert isinstance(group_page.start, int)
    assert len(group_page.groups) == len(expected_group_count)
    assert all([isinstance(s, SiteGroupResponse) for s in group_page.groups])

    assert (
        group_page.total_count == expected_total_groups
    ), f"There are only {expected_total_groups} sites available in the current config"
    if limit is not None:
        assert group_page.limit == limit
    if start is not None:
        assert group_page.start == start

    assert [(g.site_group_id, g.total_sites) for g in group_page.groups] == expected_group_count


@pytest.mark.parametrize(
    "group_name, expected_group_count",
    [
        ("Group-1", (1, 3)),
        ("Group-2", (2, 1)),
        ("Group-3", (3, 0)),
        ("Group-4", None),
    ],
)
@pytest.mark.anyio
async def test_get_site_groups(
    admin_client_auth: AsyncClient,
    group_name: str,
    expected_group_count: Optional[tuple[int, int]],
):

    response = await admin_client_auth.get(SiteGroupUri.format(group_name=group_name))

    if expected_group_count is None:
        assert response.status_code == HTTPStatus.NOT_FOUND
    else:
        assert response.status_code == HTTPStatus.OK

        body = read_response_body_string(response)
        assert len(body) > 0
        group: SiteGroupResponse = SiteGroupResponse(**json.loads(body))

        assert isinstance(group, SiteGroupResponse)
        assert group.site_group_id == expected_group_count[0]
        assert group.total_sites == expected_group_count[1]
        assert group.name == group_name
