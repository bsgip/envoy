from typing import Any, Optional

import httpx
from fastapi.testclient import TestClient

from tests.data.certificates.certificate3 import TEST_CERTIFICATE_PEM as EXPIRED_PEM
from tests.data.certificates.certificate_noreg import TEST_CERTIFICATE_PEM as UNKNOWN_PEM
from tests.integration.integration_server import cert_pem_header


def assert_status_code(response: httpx.Response, expected_status_code: int):
    """Simple assert on a response for a particular response code. Will include response body in assert message"""
    if response.status_code == expected_status_code:
        return

    body = read_response_body_string(response)
    assert response.status_code == expected_status_code, f"Got HTTP {response.status_code} expected HTTP {expected_status_code}\nResponse body:\n{body}"


def read_response_body_string(response: httpx.Response) -> str:
    """Takes a response - reads the body as a string"""
    return response.read().decode("utf-8")


def run_basic_unauthorised_tests(client: TestClient, uri: str, method: str = 'GET', body: Optional[Any] = None):
    """Runs common "unauthorised" GET requests on a particular endpoint and ensures that the endpoint is properly
    secured with our LFDI auth dependency"""

    # check expired certs don't work
    response = client.request(method=method, url=uri, data=body, headers={cert_pem_header: EXPIRED_PEM})
    assert_status_code(response, 403)

    # check unregistered certs don't work
    response = client.request(method=method, url=uri, data=body, headers={cert_pem_header: UNKNOWN_PEM})
    assert_status_code(response, 403)

    # missing cert (register as 500 as the gateway should be handling this)
    response = client.request(method=method, url=uri, data=body, headers={cert_pem_header: ''})
    assert_status_code(response, 403)
    response = client.request(method=method, url=uri, data=body)
    assert_status_code(response, 500)

    # malformed cert
    response = client.request(method=method, url=uri, data=body, headers={cert_pem_header: 'abc-123'})
    assert_status_code(response, 403)
