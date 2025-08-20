import json
import datetime as dt
from http import HTTPStatus
from typing import Optional

import pytest
import psycopg
import sqlalchemy as sa
from assertical.fixtures.postgres import generate_async_session
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.aggregator import (
    AggregatorResponse,
    AggregatorPageResponse,
    AggregatorDomain,
    AggregatorRequest,
)
from envoy_schema.admin.schema.certificate import (
    CertificateResponse,
    CertificatePageResponse,
    CertificateAssignmentRequest,
)
from envoy_schema.admin.schema import uri
from httpx import AsyncClient

from envoy.admin import crud
from envoy.server.model import AggregatorCertificateAssignment, Certificate
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


@pytest.mark.anyio
async def test_assign_certificates_to_aggregator(
    admin_client_auth: AsyncClient, pg_base_config: psycopg.Connection
) -> None:
    """Testing of the '/aggregator/{agg_id}/certificate' endpoint using POST"""
    async with generate_async_session(pg_base_config) as session:
        # create a cert specifically for the test
        await crud.certificate.create_many_certificates(
            session, [Certificate(lfdi="SOMEFAKELFDI2", expiry=dt.datetime.now() + dt.timedelta(365))]
        )
        await session.commit()

        certs = [
            CertificateAssignmentRequest(certificate_id=4),
            CertificateAssignmentRequest(lfdi="SOMEFAKELFDI1", expiry=dt.datetime.now() + dt.timedelta(365)),
            CertificateAssignmentRequest(lfdi="SOMEFAKELFDI2", expiry=dt.datetime.now() + dt.timedelta(365)),
        ]
        content = ",".join((c.model_dump_json() for c in certs))
        res_post = await admin_client_auth.post(
            uri.AggregatorCertificateListUri.format(aggregator_id=1), content=f"[{content}]"
        )

        assert res_post.status_code == HTTPStatus.CREATED

        # Ensure new entries in DB
        all_certs = await crud.certificate.select_all_certificates(session, 0, 5000)
        all_cert_lfdis = [ac.lfdi for ac in all_certs]
        assert "SOMEFAKELFDI1" in all_cert_lfdis
        assert "SOMEFAKELFDI2" in all_cert_lfdis

        all_agg_cert = await session.execute(sa.select(AggregatorCertificateAssignment))
        assert len(all_agg_cert.scalars().all()) > 5

        res_get = await admin_client_auth.get(
            uri.AggregatorCertificateListUri.format(aggregator_id=1) + _build_query_string(0, 500)
        )
        assert res_get.status_code == HTTPStatus.OK

        body = response.read_response_body_string(res_get)
        assert len(body) > 0
        cert_page: CertificatePageResponse = CertificatePageResponse.model_validate_json(body)

        assert len(cert_page.certificates) == 3 + len(certs)
        assert 4 in [c.certificate_id for c in cert_page.certificates]
        cert_page_lfdis = [c.lfdi for c in cert_page.certificates]
        assert "SOMEFAKELFDI1" in cert_page_lfdis
        assert "SOMEFAKELFDI2" in cert_page_lfdis


@pytest.mark.anyio
async def test_assign_certificates_to_aggregator_bad_id(admin_client_auth: AsyncClient) -> None:
    """Testing of the '/aggregator/{agg_id}/certificate' endpoint using POST with bad agg_id"""
    certs = [
        CertificateAssignmentRequest(certificate_id=4),
        CertificateAssignmentRequest(lfdi="SOMEFAKELFDI1", expiry=dt.datetime.now() + dt.timedelta(365)),
    ]
    content = ",".join((c.model_dump_json() for c in certs))
    res_post = await admin_client_auth.post(
        uri.AggregatorCertificateListUri.format(aggregator_id=1111), content=f"[{content}]"
    )

    assert res_post.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.anyio
async def test_assign_certificates_to_aggregator_bad_certificate_id(admin_client_auth: AsyncClient) -> None:
    """Testing of the '/aggregator/{agg_id}/certificate' endpoint using POST with non existent certificate id"""
    certs = [
        CertificateAssignmentRequest(certificate_id=4444),
        CertificateAssignmentRequest(lfdi="SOMEFAKELFDI1", expiry=dt.datetime.now() + dt.timedelta(365)),
    ]
    content = ",".join((c.model_dump_json() for c in certs))
    res_post = await admin_client_auth.post(
        uri.AggregatorCertificateListUri.format(aggregator_id=1), content=f"[{content}]"
    )

    assert res_post.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    "agg_id,cert_id,expected_ids",
    [
        (1, 1, [2, 3]),
        (1, 2, [1, 3]),
        (1, 3, [1, 2]),
        (1, 111, None),
        (111, 1, None),
    ],
)
@pytest.mark.anyio
async def test_delete_aggregator_certificate_assignments(
    admin_client_auth: AsyncClient,
    agg_id: int,
    cert_id: int,
    expected_ids: list[int],
) -> None:
    del_res = await admin_client_auth.delete(
        uri.AggregatorCertificateUri.format(aggregator_id=agg_id, certificate_id=cert_id)
    )

    if expected_ids is None:
        assert del_res.status_code == HTTPStatus.NOT_FOUND
        return

    assert del_res.status_code == HTTPStatus.NO_CONTENT

    get_res = await admin_client_auth.get(uri.AggregatorCertificateListUri.format(aggregator_id=agg_id))

    body = response.read_response_body_string(get_res)
    cert_page = CertificatePageResponse.model_validate_json(body)
    certs = cert_page.certificates

    assert [c.certificate_id for c in certs] == expected_ids


@pytest.mark.anyio
async def test_create_aggregator(admin_client_auth: AsyncClient) -> None:
    aggregator = generate_class_instance(AggregatorRequest)
    resp = await admin_client_auth.post(uri.AggregatorListUri, content=aggregator.model_dump_json())

    assert resp.status_code == HTTPStatus.CREATED

    # Confirm location header set correctly
    [agg_list_uri, aggregator_id] = resp.headers["Location"].rsplit("/", maxsplit=1)
    assert agg_list_uri == uri.AggregatorListUri
    assert int(aggregator_id)
    assert int(aggregator_id) > 3


@pytest.mark.anyio
async def test_update_aggregator(admin_client_auth: AsyncClient) -> None:
    aggregator = generate_class_instance(AggregatorRequest)
    resp = await admin_client_auth.put(uri.AggregatorUri.format(aggregator_id=1), content=aggregator.model_dump_json())

    assert resp.status_code == HTTPStatus.OK


@pytest.mark.anyio
async def test_update_aggregator_invalid_id(admin_client_auth: AsyncClient) -> None:
    aggregator = generate_class_instance(AggregatorRequest)
    resp = await admin_client_auth.put(
        uri.AggregatorUri.format(aggregator_id=1111), content=aggregator.model_dump_json()
    )

    assert resp.status_code == HTTPStatus.NOT_FOUND
