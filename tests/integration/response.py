from http import HTTPStatus
from typing import Any, Optional

import httpx

from envoy.server.api.response import SEP_XML_MIME
from envoy.server.schema.sep2.error import ErrorResponse, ReasonCodeType
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_PEM as EXPIRED_PEM
from tests.data.certificates.certificate_noreg import TEST_CERTIFICATE_PEM as UNKNOWN_PEM
from tests.integration.integration_server import cert_pem_header


def assert_response_header(response: httpx.Response,
                           expected_status_code: int,
                           expected_content_type: Optional[str] = SEP_XML_MIME):
    """Simple assert on a response for a particular response code. Will include response body in assert message in
    the event of failure. Otherwise content stream will remain unread if this assert succeeds"""

    # short cirtcuit success
    actual_content_type: str = response.headers["Content-Type"]
    if response.status_code == expected_status_code:
        if expected_content_type is None or actual_content_type == expected_content_type:
            return

    body = read_response_body_string(response)
    assert response.status_code == expected_status_code, f"Got HTTP {response.status_code} expected HTTP {expected_status_code}\nResponse body:\n{body}"
    assert expected_content_type is not None and actual_content_type == expected_content_type, f"Got Content {actual_content_type} expected {expected_content_type}\nResponse body:\n{body}"


def assert_error_response(response: httpx.Response):
    """Asserts that the response content (which will be consumed) maps to a sep2 Error object"""
    body = read_response_body_string(response)
    parsed_response: ErrorResponse = ErrorResponse.from_xml(body)
    assert type(parsed_response.reasonCode) == ReasonCodeType
    assert parsed_response.message is None or type(parsed_response.message) == str


def read_response_body_string(response: httpx.Response) -> str:
    """Takes a response - reads the body as a string"""
    return response.read().decode("utf-8")


async def run_basic_unauthorised_tests(client: httpx.AsyncClient,
                                       uri: str,
                                       method: str = 'GET',
                                       body: Optional[Any] = None):
    """Runs common "unauthorised" GET requests on a particular endpoint and ensures that the endpoint is properly
    secured with our LFDI auth dependency"""

    # check expired certs don't work
    response = await client.request(method=method, url=uri, data=body, headers={cert_pem_header: EXPIRED_PEM})
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # check unregistered certs don't work
    response = await client.request(method=method, url=uri, data=body, headers={cert_pem_header: UNKNOWN_PEM})
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # missing cert (register as 500 as the gateway should be handling this)
    response = await client.request(method=method, url=uri, data=body, headers={cert_pem_header: ''})
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)
    response = await client.request(method=method, url=uri, data=body)
    assert_response_header(response, HTTPStatus.INTERNAL_SERVER_ERROR)
    assert_error_response(response)

    # malformed cert
    response = await client.request(method=method, url=uri, data=body, headers={cert_pem_header: 'abc-123'})
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)
