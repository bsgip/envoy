import urllib.parse
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.server.schema.sep2.end_device import EndDeviceListResponse
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as VALID_PEM
from tests.integration.integration_server import cert_pem_header
from tests.integration.response import assert_response_header, read_response_body_string, run_basic_unauthorised_tests


@pytest.mark.anyio
async def test_get_empty_end_device_list(client: AsyncClient):
    """Simple test of a valid get - validates that the response looks like XML"""
    response = await client.get('/edev', headers={cert_pem_header: urllib.parse.quote(VALID_PEM)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceListResponse = EndDeviceListResponse.from_xml(body)
    assert parsed_response.EndDevice is not None, f"received body:\n{body}"
    assert len(parsed_response.EndDevice) == 0, f"received body:\n{body}"


@pytest.mark.anyio
async def test_get_empty_end_device_list_unauthorised(client: AsyncClient):
    await run_basic_unauthorised_tests(client, '/edev', method='GET')
