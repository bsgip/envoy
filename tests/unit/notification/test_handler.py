import ssl
import unittest.mock as mock

import pytest

from envoy.notification.handler import MtlsConfig, build_tls_verify


@pytest.mark.parametrize("disable_tls_verify, expected_verify", [(False, True), (True, False)])
def test_build_tls_verify_no_mtls(disable_tls_verify: bool, expected_verify: bool):
    """Without mTLS the verify argument is just the inverse of disable_tls_verify"""
    assert build_tls_verify(disable_tls_verify, None) is expected_verify


@pytest.mark.parametrize(
    "disable_tls_verify, serca_path, expect_cert_required, expect_load_verify",
    [
        (False, None, True, False),
        (False, "/ca.pem", True, True),
        (True, None, False, False),
        (True, "/ca.pem", False, False),
    ],
)
@mock.patch("envoy.notification.handler.ssl.SSLContext")
def test_build_tls_verify_mtls_ssl_context(
    mock_SSLContext: mock.MagicMock,
    disable_tls_verify: bool,
    serca_path: str | None,
    expect_cert_required: bool,
    expect_load_verify: bool,
):
    """With mTLS a properly configured SSLContext is built with the client certificate loaded from disk"""
    mock_ctx = mock.MagicMock()
    mock_SSLContext.return_value = mock_ctx

    result = build_tls_verify(disable_tls_verify, MtlsConfig("/cert.pem", "/key.pem", serca_path))

    assert result is mock_ctx
    mock_ctx.load_cert_chain.assert_called_once_with(certfile="/cert.pem", keyfile="/key.pem")
    assert mock_ctx.check_hostname is (not disable_tls_verify)
    assert mock_ctx.verify_mode == (ssl.CERT_REQUIRED if expect_cert_required else ssl.CERT_NONE)
    if expect_load_verify:
        mock_ctx.load_verify_locations.assert_called_once_with(cafile="/ca.pem")
    else:
        mock_ctx.load_verify_locations.assert_not_called()
