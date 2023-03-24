import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from server.api.depends import LFDIAuthDepends
from server.main import settings
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM
from tests.integration.integration_server import cert_pem_header


def test_generate_lfdi_from_fingerprint():
    """2030.5 defines LFDI as the first 20 octets of the sha256 certificate hash"""
    lfdi = LFDIAuthDepends._cert_fingerprint_to_lfdi(
        "0x3e4f45ab31edfe5b67e343e5e4562e31984e23e5349e2ad745672ed145ee213a"
    )  # fingerprint example from standard

    assert lfdi == "0x3e4f45ab31edfe5b67"


@pytest.mark.anyio
async def test_lfdiauthdepends_request_with_no_certpemheader_expect_500_response():
    req = Request({"type": "http", "headers": {}})

    lfdi_dep = LFDIAuthDepends(settings.cert_pem_header)

    with pytest.raises(HTTPException) as exc:
        await lfdi_dep(req)

    assert exc.value.status_code == 500


@pytest.mark.parametrize("mock_db", ["server.api.depends.db"], indirect=True)
@pytest.mark.anyio
async def test_lfdiauthdepends_request_with_unregistered_cert_expect_403_response(
    mocker, mock_db
):
    mocker.patch("server.crud.auth.select_client_ids_using_lfdi", return_value=None)
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_pem_header: TEST_CERTIFICATE_PEM.decode('utf-8')}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_pem_header)

    with pytest.raises(HTTPException) as exc:
        await lfdi_dep(req)

    assert exc.value.status_code == 403
