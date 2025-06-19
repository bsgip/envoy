import json
from http import HTTPStatus
from typing import Optional

import pytest
import psycopg
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.aggregator import AggregatorResponse, AggregatorPageResponse, AggregatorDomain
from envoy_schema.admin.schema.certificate import CertificateResponse, CertificatePageResponse
from envoy_schema.admin.schema import uri
from httpx import AsyncClient

from envoy.admin import crud
from tests.integration import response


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
    pg_base_config: psycopg.Connection,
    start: int,
    limit: int,
    expected_agg_ids: list[int],
) -> None:
    expected_total_aggs: int
    async with generate_async_session(pg_base_config) as session:
        expected_total_aggs = await crud.aggregator.count_all_aggregators(session)

    res = await admin_client_auth.get(uri.AggregatorListUri + _build_query_string(start, limit))
    assert res.status_code == HTTPStatus.OK

    body = response.read_response_body_string(res)
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
) -> None:
    res = await admin_client_auth.get(uri.AggregatorUri.format(aggregator_id=agg_id))
    if expected_name is None or expected_domains is None:
        assert res.status_code == HTTPStatus.NOT_FOUND
    else:
        assert res.status_code == HTTPStatus.OK

        body = response.read_response_body_string(res)
        assert len(body) > 0
        agg: AggregatorResponse = AggregatorResponse(**json.loads(body))

        assert agg.aggregator_id == agg_id
        assert agg.name == expected_name
        assert all([isinstance(s, AggregatorDomain) for s in agg.domains])
        assert sorted(expected_domains) == sorted([d.domain for d in agg.domains])


@pytest.mark.parametrize(
    "start, limit, agg_id, expected_cert_ids",
    [
        (None, None, 1, [1, 2, 3]),
        (0, 10, 1, [1, 2, 3]),
        (2, 10, 1, [3]),
        (None, 2, 1, [1, 2]),
        (None, None, 2, [4]),
        (None, None, 3, [5]),
        (None, None, 4, None),
    ],
)
@pytest.mark.anyio
async def test_get_aggregator_certificates(
    admin_client_auth: AsyncClient,
    pg_base_config: psycopg.Connection,
    start: int,
    limit: int,
    agg_id: int,
    expected_cert_ids: list[int],
) -> None:
    """Parametrized testing of the '/aggregator/{agg_id}/certificates' endpoint using GET"""
    expected_total_certs: int
    async with generate_async_session(pg_base_config) as session:
        expected_total_certs = await crud.certificate.count_certificates_for_aggregator(session, agg_id)

    res = await admin_client_auth.get(
        uri.AggregatorCertificateListUri.format(aggregator_id=agg_id) + _build_query_string(start, limit)
    )

    if agg_id is None or expected_cert_ids is None:
        assert res.status_code == HTTPStatus.NOT_FOUND
        return

    assert res.status_code == HTTPStatus.OK

    body = response.read_response_body_string(res)
    assert len(body) > 0
    cert_page: CertificatePageResponse = CertificatePageResponse.model_validate_json(body)

    assert isinstance(cert_page.limit, int)
    assert isinstance(cert_page.total_count, int)
    assert isinstance(cert_page.start, int)
    assert len(cert_page.certificates) == len(expected_cert_ids)
    assert all([isinstance(s, CertificateResponse) for s in cert_page.certificates])

    assert cert_page.total_count == expected_total_certs
    if limit is not None:
        assert cert_page.limit == limit
    if start is not None:
        assert cert_page.start == start

    assert [a.certificate_id for a in cert_page.certificates] == expected_cert_ids
