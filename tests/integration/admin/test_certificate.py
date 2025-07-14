from http import HTTPStatus

import pytest
import httpx
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.certificate import CertificateRequest, CertificateResponse, CertificatePageResponse
from envoy_schema.admin.schema import uri


@pytest.mark.anyio
async def test_get_all_certificates(admin_client_auth: httpx.AsyncClient) -> None:
    resp = await admin_client_auth.get(uri.CertificateListUri, params={"limit": 3})
    assert resp.status_code == HTTPStatus.OK
    cert_page_resp = CertificatePageResponse.model_validate_json(resp.content)
    assert len(cert_page_resp.certificates) == 3


@pytest.mark.anyio
async def test_get_single_certificate(admin_client_auth: httpx.AsyncClient) -> None:
    resp = await admin_client_auth.get(uri.CertificateUri.format(certificate_id=1))
    assert resp.status_code == HTTPStatus.OK
    cert_resp = CertificateResponse.model_validate_json(resp.content)
    assert cert_resp.certificate_id == 1


@pytest.mark.anyio
async def test_get_single_certificate_invalid_id(admin_client_auth: httpx.AsyncClient) -> None:
    resp = await admin_client_auth.get(uri.CertificateUri.format(certificate_id=1111))
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.anyio
async def test_create_certificate(admin_client_auth: httpx.AsyncClient) -> None:
    certificate = generate_class_instance(CertificateRequest)
    resp = await admin_client_auth.post(uri.CertificateListUri, content=certificate.model_dump_json())

    assert resp.status_code == HTTPStatus.CREATED

    # Confirm location header set correctly
    [cert_list_uri, certificate_id] = resp.headers["Location"].rsplit("/", maxsplit=1)
    assert cert_list_uri == uri.CertificateListUri
    assert int(certificate_id)
    assert int(certificate_id) > 5


@pytest.mark.anyio
async def test_update_certificate(admin_client_auth: httpx.AsyncClient) -> None:
    certificate = generate_class_instance(CertificateRequest)
    resp = await admin_client_auth.put(
        uri.CertificateUri.format(certificate_id=1), content=certificate.model_dump_json()
    )

    assert resp.status_code == HTTPStatus.OK


@pytest.mark.anyio
async def test_update_certificate_invalid_id(admin_client_auth: httpx.AsyncClient) -> None:
    certificate = generate_class_instance(CertificateRequest)
    resp = await admin_client_auth.put(
        uri.CertificateUri.format(certificate_id=1111), content=certificate.model_dump_json()
    )

    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.anyio
async def test_delete_certificate(admin_client_auth: httpx.AsyncClient) -> None:
    resp = await admin_client_auth.delete(uri.CertificateUri.format(certificate_id=1))

    assert resp.status_code == HTTPStatus.NO_CONTENT


@pytest.mark.anyio
async def test_delete_certificate_invalid_id(admin_client_auth: httpx.AsyncClient) -> None:
    resp = await admin_client_auth.delete(uri.CertificateUri.format(certificate_id=1111))

    assert resp.status_code == HTTPStatus.NOT_FOUND
