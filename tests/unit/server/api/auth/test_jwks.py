import pytest

from envoy.server.api.auth.jwks import decode_b64_bytes_to_int, ensure_bytes, rsa_pem_from_jwk


@pytest.mark.parametrize("val", [(""), ("abc-123-DEF#== "), (" ")])
def test_ensure_bytes(val: str):
    """Simple sanity check to ensure no exceptions are being raised on some known good values"""
    b = val.encode("utf-8")
    assert ensure_bytes(val) == b
    assert ensure_bytes(b) == b


@pytest.mark.parametrize(
    "val",
    [
        ("AQAB"),
        (
            "spvQcXWqYrMcvcqQmfSMYnbUC8U03YctnXyLIBe148OzhBrgdAOmPfMfJi_tUW8L9svVGpk5qG6dN0n669cRHKqU52GnG0tlyYXmzFC1hzHVgQz9ehve4tlJ7uw936XIUOAOxx3X20zdpx7gm4zHx4j2ZBlXskAj6U3adpHQNuwUE6kmngJWR-deWlEigMpRsvUVQ2O5h0-RSq8Wr_x7ud3K6GTtrzARamz9uk2IXatKYdnj5Jrk2jLY6nWt-GtxlA_l9XwIrOl6Sqa_pOGIpS01JKdxKvpBC9VdS8oXB-7P5qLksmv7tq-SbbiOec0cvU7WP7vURv104V4FiI_qoQ"  # noqa
        ),
    ],
)
def test_decode_b64_bytes_to_int(val: str):
    """Simple sanity check to ensure no exceptions are being raised on some known good values"""
    result = decode_b64_bytes_to_int(val)
    assert isinstance(result, int)
    assert result != 0


@pytest.mark.parametrize(
    "e, n",
    [
        (
            "AQAB",
            "spvQcXWqYrMcvcqQmfSMYnbUC8U03YctnXyLIBe148OzhBrgdAOmPfMfJi_tUW8L9svVGpk5qG6dN0n669cRHKqU52GnG0tlyYXmzFC1hzHVgQz9ehve4tlJ7uw936XIUOAOxx3X20zdpx7gm4zHx4j2ZBlXskAj6U3adpHQNuwUE6kmngJWR-deWlEigMpRsvUVQ2O5h0-RSq8Wr_x7ud3K6GTtrzARamz9uk2IXatKYdnj5Jrk2jLY6nWt-GtxlA_l9XwIrOl6Sqa_pOGIpS01JKdxKvpBC9VdS8oXB-7P5qLksmv7tq-SbbiOec0cvU7WP7vURv104V4FiI_qoQ",  # noqa e501
        ),
    ],
)
def test_rsa_pem_from_jwk(n: str, e: str):
    """Simple sanity check to ensure no exceptions are being raised on some known good values"""
    result = rsa_pem_from_jwk(decode_b64_bytes_to_int(n), decode_b64_bytes_to_int(e))
    assert isinstance(result, bytes)
    assert len(result) != 0
