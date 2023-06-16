import json
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient

from envoy.admin.schema.site import SitePageResponse, SiteResponse
from envoy.admin.schema.uri import SiteUri
from tests.integration.response import read_response_body_string


def _build_query_string(start: Optional[int], limit: Optional[int]) -> str:
    query = "?"
    if start is not None:
        query = query + f"&start={start}"
    if limit is not None:
        query = query + f"&limit={limit}"
    return query


@pytest.mark.parametrize(
    "start, limit, expected_site_ids",
    [
        (None, None, [1, 2, 3, 4]),
        (0, 10, [1, 2, 3, 4]),
        (2, 10, [3, 4]),
        (None, 2, [1, 2]),
        (2, 2, [3, 4]),
        (3, 2, [4]),
    ],
)
@pytest.mark.anyio
async def test_get_all_sites(admin_client_auth: AsyncClient, start: int, limit: int, expected_site_ids: list[int]):
    response = await admin_client_auth.get(SiteUri + _build_query_string(start, limit))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    site_page: SitePageResponse = SitePageResponse(**json.loads(body))

    assert isinstance(site_page.limit, int)
    assert isinstance(site_page.total_count, int)
    assert isinstance(site_page.start, int)
    assert len(site_page.sites) == len(expected_site_ids)
    assert all([isinstance(s, SiteResponse) for s in site_page.sites])

    assert site_page.total_count == 4, "There are only 4 sites available in the current config"
    if limit is not None:
        assert site_page.limit == limit
    if start is not None:
        assert site_page.start == start

    assert [s.site_id for s in site_page.sites] == expected_site_ids
