import json
from http import HTTPStatus
from typing import Optional

import pytest
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.aggregator import AggregatorDomain, AggregatorPageResponse, AggregatorResponse
from envoy_schema.admin.schema.uri import AggregatorListUri, AggregatorUri
from httpx import AsyncClient

from envoy.admin.crud.aggregator import count_all_aggregators
from tests.integration.response import read_response_body_string


def _build_query_string(start: Optional[int], limit: Optional[int]) -> str:
    query = "?"
    if start is not None:
        query = query + f"&start={start}"
    if limit is not None:
        query = query + f"&limit={limit}"
    return query


@pytest.mark.parametrize(
    "start, limit, expected_agg_ids",
    [
        (None, None, [1, 2, 3]),
        (0, 10, [1, 2, 3]),
        (2, 10, [3]),
        (None, 2, [1, 2]),
        (2, 2, [3]),
    ],
)
@pytest.mark.anyio
async def test_get_all_aggregators(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    expected_agg_ids: list[int],
):
    expected_total_aggs: int
    async with generate_async_session(pg_base_config) as session:
        expected_total_aggs = await count_all_aggregators(session)

    response = await admin_client_auth.get(AggregatorListUri + _build_query_string(start, limit))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    agg_page: AggregatorPageResponse = AggregatorPageResponse(**json.loads(body))

    assert isinstance(agg_page.limit, int)
    assert isinstance(agg_page.total_count, int)
    assert isinstance(agg_page.start, int)
    assert len(agg_page.aggregators) == len(expected_agg_ids)
    assert all([isinstance(s, AggregatorResponse) for s in agg_page.aggregators])

    assert agg_page.total_count == expected_total_aggs
    if limit is not None:
        assert agg_page.limit == limit
    if start is not None:
        assert agg_page.start == start

    assert [a.aggregator_id for a in agg_page.aggregators] == expected_agg_ids


@pytest.mark.parametrize(
    "agg_id, expected_name, expected_domains",
    [
        (1, "Aggregator 1", ["example.com", "another.example.com"]),
        (2, "Aggregator 2", ["example.com"]),
        (3, "Aggregator 3", ["example.com"]),
        (4, None, None),
    ],
)
@pytest.mark.anyio
async def test_get_aggregator(
    admin_client_auth: AsyncClient,
    agg_id: int,
    expected_name: Optional[str],
    expected_domains: Optional[list[str]],
):
    response = await admin_client_auth.get(AggregatorUri.format(aggregator_id=agg_id))
    if expected_name is None or expected_domains is None:
        assert response.status_code == HTTPStatus.NOT_FOUND
    else:
        assert response.status_code == HTTPStatus.OK

        body = read_response_body_string(response)
        assert len(body) > 0
        agg: AggregatorResponse = AggregatorResponse(**json.loads(body))

        assert agg.aggregator_id == agg_id
        assert agg.name == expected_name
        assert all([isinstance(s, AggregatorDomain) for s in agg.domains])
        assert sorted(expected_domains) == sorted([d.domain for d in agg.domains])
