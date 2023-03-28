import unittest.mock as mock
from urllib.parse import quote_from_bytes

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from envoy.server.api.depends import LFDIAuthDepends
from envoy.server.main import settings
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_1
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_1
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_2
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_2
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_3
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_3
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_4
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_4
from tests.integration.integration_server import cert_pem_header


def test_generate_lfdi_from_fingerprint():
    """2030.5 defines LFDI as the first 20 octets of the sha256 certificate hash. This test
    is pulled direct from an example in the standard"""
    lfdi = LFDIAuthDepends._cert_fingerprint_to_lfdi(
        "3e4f45ab31edfe5b67e343e5e4562e31984e23e5349e2ad745672ed145ee213a"
    )

    assert lfdi == "3e4f45ab31edfe5b67e343e5e4562e31984e23e5"


def test_generate_lfdi_from_pem():
    """Tests our known certificate PEM's convert to the expected LFDI"""
    lfdi_dep = LFDIAuthDepends(settings.cert_pem_header)
    assert TEST_CERTIFICATE_LFDI_1 == lfdi_dep.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_1))
    assert TEST_CERTIFICATE_LFDI_2 == lfdi_dep.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_2))
    assert TEST_CERTIFICATE_LFDI_3 == lfdi_dep.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_3))
    assert TEST_CERTIFICATE_LFDI_4 == lfdi_dep.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_4))


@pytest.mark.anyio
async def test_lfdiauthdepends_request_with_no_certpemheader_expect_500_response():
    req = Request({"type": "http", "headers": {}})

    lfdi_dep = LFDIAuthDepends(settings.cert_pem_header)

    with pytest.raises(HTTPException) as exc:
        await lfdi_dep(req)

    assert exc.value.status_code == 500


@pytest.mark.anyio
@mock.patch("envoy.server.crud.auth.select_client_ids_using_lfdi")
async def test_lfdiauthdepends_request_with_unregistered_cert_expect_403_response(
    mock_select_client_ids_using_lfdi: mock.MagicMock
):
    # Arrange
    mock_select_client_ids_using_lfdi.return_value = None
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_pem_header: TEST_CERTIFICATE_PEM_1.decode('utf-8')}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_pem_header)

    # Act

    with pytest.raises(HTTPException) as exc:
        await lfdi_dep(req)

    # Assert

    assert exc.value.status_code == 403
    mock_select_client_ids_using_lfdi.assert_called_once()
