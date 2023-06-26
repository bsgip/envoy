from http import HTTPStatus

import pytest
from httpx import AsyncClient
from test_api import ALL_ENDPOINTS_WITH_SUPPORTED_METHODS

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as VALID_CERT
from tests.integration.http import HTTPMethod
from tests.integration.response import assert_response_header

UPPERCASE_CERT_HEADER = "x-Header-With-UpperCASE"
LOWERCASE_CERT_HEADER = "x-header-with-lower-case"

GET_URIS = [(uri) for (valid_methods, uri) in ALL_ENDPOINTS_WITH_SUPPORTED_METHODS if HTTPMethod.GET in valid_methods]


@pytest.mark.cert_header(UPPERCASE_CERT_HEADER)
@pytest.mark.parametrize("uri", GET_URIS)
@pytest.mark.anyio
async def test_custom_cert_header_with_uppercase(uri: str, client: AsyncClient):
    """Validates that changing the default setting for the cert_header to include uppercase values doesn't cause
    problems (this is a regression test for catching a HTTP 500 spotted in a custom environment)"""
    resp_case_match = await client.get(uri, headers={UPPERCASE_CERT_HEADER: VALID_CERT})
    assert_response_header(resp_case_match, HTTPStatus.OK)

    resp_case_mismatch = await client.get(uri, headers={UPPERCASE_CERT_HEADER.lower(): VALID_CERT})
    assert_response_header(resp_case_mismatch, HTTPStatus.OK)


@pytest.mark.cert_header(LOWERCASE_CERT_HEADER)
@pytest.mark.parametrize("uri", GET_URIS)
@pytest.mark.anyio
async def test_custom_cert_header_with_lowercase(uri: str, client: AsyncClient):
    """Validates that changing the default setting for the cert_header to include uppercase values doesn't cause
    problems (this is a regression test for catching a HTTP 500 spotted in a custom environment)"""
    resp_case_match = await client.get(uri, headers={LOWERCASE_CERT_HEADER: VALID_CERT})
    assert_response_header(resp_case_match, HTTPStatus.OK)

    resp_case_mismatch = await client.get(uri, headers={LOWERCASE_CERT_HEADER.upper(): VALID_CERT})
    assert_response_header(resp_case_mismatch, HTTPStatus.OK)
