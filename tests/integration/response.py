from http import HTTPStatus
from typing import Any, Optional

import httpx
from envoy_schema.server.schema.sep2.error import ErrorResponse
from envoy_schema.server.schema.sep2.types import ReasonCodeType

from envoy.server.api.response import LOCATION_HEADER_NAME, SEP_XML_MIME
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as VALID_FINGERPRINT
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_FINGERPRINT as EXPIRED_FINGERPRINT
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_PEM as EXPIRED_PEM
from tests.data.certificates.certificate_noreg import TEST_CERTIFICATE_FINGERPRINT as UNKNOWN_FINGERPRINT
from tests.data.certificates.certificate_noreg import TEST_CERTIFICATE_PEM as UNKNOWN_PEM
from tests.integration.integration_server import cert_header
from tests.unit.jwt import generate_rs256_jwt


def assert_response_header(
    response: httpx.Response, expected_status_code: int, expected_content_type: Optional[str] = SEP_XML_MIME
):
    """Simple assert on a response for a particular response code. Will include response body in assert message in
    the event of failure. Otherwise content stream will remain unread if this assert succeeds"""

    # short circuit success
    actual_content_type: Optional[str] = (
        response.headers["Content-Type"] if "Content-Type" in response.headers else None
    )
    if response.status_code == expected_status_code:
        if expected_content_type is None or actual_content_type == expected_content_type:
            return

    body = read_response_body_string(response)
    assert (
        response.status_code == expected_status_code
    ), f"Got HTTP {response.status_code} expected HTTP {expected_status_code} request: {response.request.method} {response.request.url.path}\nResponse body:\n{body}"  # noqa E501
    assert (
        expected_content_type is not None and actual_content_type == expected_content_type
    ), f"Got Content {actual_content_type} expected {expected_content_type} request:  {response.request.method} {response.request.url.path}\nResponse body:\n{body}"  # noqa E501


def assert_error_response(response: httpx.Response):
    """Asserts that the response content (which will be consumed) maps to a sep2 Error object"""
    body = read_response_body_string(response)
    if response.request.method == "HEAD":
        assert len(body) == 0, "Expected an empty response for a HEAD request"
        return  # can't validate something that isn't there

    parsed_response: ErrorResponse = ErrorResponse.from_xml(body)
    assert isinstance(parsed_response.reasonCode, ReasonCodeType)
    assert parsed_response.message is None or isinstance(parsed_response.message, str)


def read_location_header(response: httpx.Response) -> str:
    """Attempts to read the Location header - throws an exception if not found"""
    if LOCATION_HEADER_NAME not in response.headers:
        raise Exception(
            f"Header '{LOCATION_HEADER_NAME}' not returned ({response.status_code}). Headers: {response.headers.keys()}"
        )
    return response.headers[LOCATION_HEADER_NAME]


def read_response_body_string(response: httpx.Response) -> str:
    """Takes a response - reads the body as a string"""
    return response.read().decode("utf-8")


def _apply_headers(base_headers: Optional[dict[str, str]], add_headers: dict[str, str]) -> dict[str, str]:
    if base_headers:
        return dict(base_headers) | add_headers
    else:
        return add_headers


async def run_basic_unauthorised_tests(
    client: httpx.AsyncClient,
    uri: str,
    method: str = "GET",
    body: Optional[Any] = None,
    base_headers: Optional[dict[str, str]] = None,
    test_unrecognised_cert: bool = True,
):
    """Runs common "unauthorised" GET requests on a particular endpoint and ensures that the endpoint is properly
    secured with our LFDI auth dependency"""

    # check expired certs don't work
    response = await client.request(
        method=method, url=uri, content=body, headers=_apply_headers(base_headers, {cert_header: EXPIRED_PEM})
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)
    response = await client.request(
        method=method, url=uri, content=body, headers=_apply_headers(base_headers, {cert_header: EXPIRED_FINGERPRINT})
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # check unregistered certs don't work
    if test_unrecognised_cert:
        response = await client.request(
            method=method, url=uri, content=body, headers=_apply_headers(base_headers, {cert_header: UNKNOWN_PEM})
        )
        assert_response_header(response, HTTPStatus.FORBIDDEN)
        assert_error_response(response)
        response = await client.request(
            method=method,
            url=uri,
            content=body,
            headers=_apply_headers(base_headers, {cert_header: UNKNOWN_FINGERPRINT}),
        )
        assert_response_header(response, HTTPStatus.FORBIDDEN)
        assert_error_response(response)

    # missing cert (register as 500 as the gateway should be handling this)
    response = await client.request(
        method=method, url=uri, content=body, headers=_apply_headers(base_headers, {cert_header: ""})
    )
    assert_response_header(response, HTTPStatus.INTERNAL_SERVER_ERROR)
    assert_error_response(response)
    response = await client.request(method=method, url=uri, content=body, headers=base_headers)
    assert_response_header(response, HTTPStatus.INTERNAL_SERVER_ERROR)
    assert_error_response(response)

    # malformed cert
    response = await client.request(
        method=method, url=uri, content=body, headers=_apply_headers(base_headers, {cert_header: "abc-123"})
    )
    assert_response_header(response, HTTPStatus.BAD_REQUEST)
    assert_error_response(response)


async def run_azure_ad_unauthorised_tests(
    client: httpx.AsyncClient, uri: str, method: str = "GET", body: Optional[Any] = None
):
    """Runs Unauthorised tests with respect to Azure Active Directory bearer tokens, These will only
    pass if the Azure AD auth dependency is enabled.

    This wont exhaustively enumerate all the ways the token can be invalid - unit test coverage will handle that"""

    # No azure AD bearer token
    response = await client.request(method=method, url=uri, content=body, headers={cert_header: VALID_FINGERPRINT})
    assert_response_header(response, HTTPStatus.UNAUTHORIZED)
    assert_error_response(response)

    # Missing token value
    response = await client.request(
        method=method, url=uri, content=body, headers={cert_header: VALID_FINGERPRINT, "Authorization": "Bearer "}
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # Malformed token
    response = await client.request(
        method=method,
        url=uri,
        content=body,
        headers={cert_header: VALID_FINGERPRINT, "Authorization": "Bearer eyNotAToken"},
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # Expired token
    token = generate_rs256_jwt(expired=True)
    response = await client.request(
        method=method,
        url=uri,
        content=body,
        headers={cert_header: VALID_FINGERPRINT, "Authorization": f"Bearer {token}"},
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # Invalid audience
    token = generate_rs256_jwt(aud="invalid-audience")
    response = await client.request(
        method=method,
        url=uri,
        content=body,
        headers={cert_header: VALID_FINGERPRINT, "Authorization": f"Bearer {token}"},
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # Invalid kid
    token = generate_rs256_jwt(kid_override="invalid-kid")
    response = await client.request(
        method=method,
        url=uri,
        content=body,
        headers={cert_header: VALID_FINGERPRINT, "Authorization": f"Bearer {token}"},
    )
    assert_response_header(response, HTTPStatus.UNAUTHORIZED)
    assert_error_response(response)
