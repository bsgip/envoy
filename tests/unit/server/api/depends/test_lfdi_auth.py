import unittest.mock as mock
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_from_bytes

import pytest
from assertical.fake.generator import generate_class_instance
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends
from envoy.server.crud.auth import ClientIdDetails
from envoy.server.main import settings
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID
from envoy.server.model.site import Site
from envoy.server.request_scope import CertificateType
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as TEST_CERTIFICATE_FINGERPRINT_1
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_1
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_1
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_SFDI as TEST_CERTIFICATE_SFDI_1
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_FINGERPRINT as TEST_CERTIFICATE_FINGERPRINT_2
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_2
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_2
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_FINGERPRINT as TEST_CERTIFICATE_FINGERPRINT_3
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_3
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_3
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as TEST_CERTIFICATE_FINGERPRINT_4
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_LFDI as TEST_CERTIFICATE_LFDI_4
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as TEST_CERTIFICATE_PEM_4
from tests.integration.integration_server import cert_header


def test_generate_lfdi_from_fingerprint():
    """sep2 defines LFDI as the first 20 octets of the sha256 certificate hash. This test
    is pulled direct from an example in the standard"""
    assert TEST_CERTIFICATE_LFDI_1 == LFDIAuthDepends.generate_lfdi_from_fingerprint(TEST_CERTIFICATE_FINGERPRINT_1)
    assert TEST_CERTIFICATE_LFDI_2 == LFDIAuthDepends.generate_lfdi_from_fingerprint(TEST_CERTIFICATE_FINGERPRINT_2)
    assert TEST_CERTIFICATE_LFDI_3 == LFDIAuthDepends.generate_lfdi_from_fingerprint(TEST_CERTIFICATE_FINGERPRINT_3)
    assert TEST_CERTIFICATE_LFDI_4 == LFDIAuthDepends.generate_lfdi_from_fingerprint(TEST_CERTIFICATE_FINGERPRINT_4)


def test_generate_lfdi_from_pem():
    """Tests our known certificate PEM's convert to the expected LFDI"""
    assert TEST_CERTIFICATE_LFDI_1 == LFDIAuthDepends.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_1))
    assert TEST_CERTIFICATE_LFDI_2 == LFDIAuthDepends.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_2))
    assert TEST_CERTIFICATE_LFDI_3 == LFDIAuthDepends.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_3))
    assert TEST_CERTIFICATE_LFDI_4 == LFDIAuthDepends.generate_lfdi_from_pem(quote_from_bytes(TEST_CERTIFICATE_PEM_4))


@pytest.mark.anyio
@pytest.mark.parametrize("allow_device_registration", [True, False])
async def test_lfdiauthdepends_request_with_no_certpemheader_expect_500_response(allow_device_registration: bool):
    req = Request({"type": "http", "headers": {}})

    lfdi_dep = LFDIAuthDepends(settings.cert_header, allow_device_registration)

    with pytest.raises(HTTPException) as exc:
        await lfdi_dep(req)

    assert exc.value.status_code == 500


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.lfdi_auth.select_single_site_with_sfdi")
@mock.patch("envoy.server.api.depends.lfdi_auth.select_all_client_id_details")
@mock.patch("envoy.server.api.depends.lfdi_auth.db")
@pytest.mark.parametrize(
    "bad_cert_header",
    ["test-abc123", TEST_CERTIFICATE_PEM_1.decode("utf-8")[4:], TEST_CERTIFICATE_LFDI_1[2:], TEST_CERTIFICATE_SFDI_1],
)
async def test_lfdiauthdepends_malformed_cert_fails_with_bad_request(
    mock_db: mock.MagicMock,
    mock_select_all_client_id_details: mock.MagicMock,
    mock_select_single_site_with_sfdi: mock.MagicMock,
    bad_cert_header: str,
):
    # Arrange
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_header: bad_cert_header}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_header, allow_device_registration=True)

    # Act
    with pytest.raises(HTTPException) as exc:
        await lfdi_dep(req)

    # Assert
    assert exc.value.status_code == 400
    mock_select_all_client_id_details.assert_not_called()
    mock_select_single_site_with_sfdi.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.lfdi_auth.select_single_site_with_sfdi")
@mock.patch("envoy.server.api.depends.lfdi_auth.select_all_client_id_details")
@mock.patch("envoy.server.api.depends.lfdi_auth.db")
async def test_lfdiauthdepends_unregistered_cert_no_device_registration(
    mock_db: mock.MagicMock,
    mock_select_all_client_id_details: mock.MagicMock,
    mock_select_single_site_with_sfdi: mock.MagicMock,
):
    # Arrange
    mock_select_all_client_id_details.return_value = []
    mock_select_single_site_with_sfdi.return_value = None
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_header: TEST_CERTIFICATE_PEM_1.decode("utf-8")}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_header, allow_device_registration=False)

    # Act
    with pytest.raises(HTTPException) as exc:
        await lfdi_dep(req)

    # Assert
    assert exc.value.status_code == 403
    mock_select_all_client_id_details.assert_called_once()
    mock_select_single_site_with_sfdi.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.lfdi_auth.select_single_site_with_sfdi")
@mock.patch("envoy.server.api.depends.lfdi_auth.select_all_client_id_details")
@mock.patch("envoy.server.api.depends.lfdi_auth.db")
async def test_lfdiauthdepends_unregistered_cert_with_device_registration(
    mock_db: mock.MagicMock,
    mock_select_all_client_id_details: mock.MagicMock,
    mock_select_single_site_with_sfdi: mock.MagicMock,
):
    # Arrange
    mock_select_all_client_id_details.return_value = []
    mock_select_single_site_with_sfdi.return_value = None
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_header: TEST_CERTIFICATE_PEM_1.decode("utf-8")}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_header, allow_device_registration=True)

    # Act
    await lfdi_dep(req)

    # Assert
    assert req.state.aggregator_id is None
    assert req.state.site_id is None
    assert req.state.source == CertificateType.DEVICE_CERTIFICATE
    assert req.state.lfdi == TEST_CERTIFICATE_LFDI_1
    assert req.state.sfdi == int(TEST_CERTIFICATE_SFDI_1)

    mock_select_all_client_id_details.assert_called_once()
    mock_select_single_site_with_sfdi.assert_called_once()


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.lfdi_auth.select_single_site_with_sfdi")
@mock.patch("envoy.server.api.depends.lfdi_auth.select_all_client_id_details")
@mock.patch("envoy.server.api.depends.lfdi_auth.db")
async def test_lfdiauthdepends_site_specific_cert(
    mock_db: mock.MagicMock,
    mock_select_all_client_id_details: mock.MagicMock,
    mock_select_single_site_with_sfdi: mock.MagicMock,
):
    SITE_ID = 154125
    SFDI = 54112

    # Arrange
    mock_select_all_client_id_details.return_value = []
    mock_select_single_site_with_sfdi.return_value = generate_class_instance(Site, site_id=SITE_ID, sfdi=SFDI)
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_header: TEST_CERTIFICATE_PEM_1.decode("utf-8")}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_header, allow_device_registration=True)

    # Act
    await lfdi_dep(req)

    # Assert
    assert req.state.aggregator_id is None
    assert req.state.site_id == SITE_ID
    assert req.state.source == CertificateType.DEVICE_CERTIFICATE
    assert req.state.lfdi == TEST_CERTIFICATE_LFDI_1
    assert req.state.sfdi == int(TEST_CERTIFICATE_SFDI_1)

    mock_select_all_client_id_details.assert_called_once()
    mock_select_single_site_with_sfdi.assert_called_once()
    mock_select_single_site_with_sfdi.call_args_list[0].kwargs["sfdi"] == SFDI
    mock_select_single_site_with_sfdi.call_args_list[0].kwargs["aggregator_id"] == NULL_AGGREGATOR_ID


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.lfdi_auth.select_single_site_with_sfdi")
@mock.patch("envoy.server.api.depends.lfdi_auth.select_all_client_id_details")
@mock.patch("envoy.server.api.depends.lfdi_auth.db")
async def test_lfdiauthdepends_aggregator_specific_cert(
    mock_db: mock.MagicMock,
    mock_select_all_client_id_details: mock.MagicMock,
    mock_select_single_site_with_sfdi: mock.MagicMock,
):
    AGG_ID = 51412
    # Arrange
    mock_select_all_client_id_details.return_value = [
        ClientIdDetails("doesnotexist", 1, datetime.now(timezone.utc) + timedelta(hours=1)),
        ClientIdDetails(TEST_CERTIFICATE_LFDI_1, AGG_ID, datetime.now(timezone.utc) + timedelta(hours=1)),
    ]
    mock_select_single_site_with_sfdi.return_value = None
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_header: TEST_CERTIFICATE_PEM_1.decode("utf-8")}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_header, allow_device_registration=True)

    # Act
    await lfdi_dep(req)

    # Assert
    assert req.state.aggregator_id == AGG_ID
    assert req.state.site_id is None
    assert req.state.source == CertificateType.AGGREGATOR_CERTIFICATE
    assert req.state.lfdi == TEST_CERTIFICATE_LFDI_1
    assert req.state.sfdi == int(TEST_CERTIFICATE_SFDI_1)

    mock_select_all_client_id_details.assert_called_once()
    mock_select_single_site_with_sfdi.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.lfdi_auth.select_single_site_with_sfdi")
@mock.patch("envoy.server.api.depends.lfdi_auth.select_all_client_id_details")
@mock.patch("envoy.server.api.depends.lfdi_auth.db")
async def test_lfdiauthdepends_aggregator_specific_cert_thats_expired(
    mock_db: mock.MagicMock,
    mock_select_all_client_id_details: mock.MagicMock,
    mock_select_single_site_with_sfdi: mock.MagicMock,
):
    """Tests that if the DB is reporting that an aggregator cert is expired that it doesn't accidently
    get classified as a new device cert"""
    AGG_ID = 51412
    # Arrange
    mock_select_all_client_id_details.return_value = [
        ClientIdDetails("doesnotexist", 1, datetime.now(timezone.utc) + timedelta(hours=1)),
        ClientIdDetails(TEST_CERTIFICATE_LFDI_1, AGG_ID, datetime.now(timezone.utc) - timedelta(hours=1)),
    ]
    mock_select_single_site_with_sfdi.return_value = None
    req = Request(
        {
            "type": "http",
            "headers": Headers({cert_header: TEST_CERTIFICATE_PEM_1.decode("utf-8")}).raw,
        }
    )

    lfdi_dep = LFDIAuthDepends(settings.cert_header, allow_device_registration=True)

    # Act
    with pytest.raises(HTTPException):
        await lfdi_dep(req)

    mock_select_all_client_id_details.assert_called_once()
    mock_select_single_site_with_sfdi.assert_not_called()
