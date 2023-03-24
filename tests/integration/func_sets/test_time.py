import urllib.parse
from datetime import datetime
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from server.schema.sep2.time import TimeResponse
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as VALID_PEM
from tests.integration.integration_server import cert_pem_header
from tests.integration.response import assert_response_header, read_response_body_string, run_basic_unauthorised_tests


@pytest.mark.anyio
async def test_get_time_resource(client: AsyncClient):
    """Simple test of a valid get - validates that the response looks like XML"""
    response = await client.get('/tm', headers={cert_pem_header: urllib.parse.quote(VALID_PEM)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TimeResponse = TimeResponse.from_xml(body)

    diff = datetime.now().timestamp() - parsed_response.currentTime
    assert diff > 0 and diff < 20, f"Diff between now and the timestamp value is {diff}. Was expected to be small"
    assert parsed_response.quality == 4


@pytest.mark.anyio
async def test_get_time_resource_unauthorised(client: AsyncClient):
    await run_basic_unauthorised_tests(client, '/tm', method='GET')


@pytest.mark.anyio
async def test_get_time_resource_invalid_methods(client: AsyncClient):
    response = await client.put('/tm', headers={cert_pem_header: VALID_PEM})
    assert_response_header(response, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type=None)

    response = await client.delete('/tm', headers={cert_pem_header: VALID_PEM})
    assert_response_header(response, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type=None)

    response = await client.post('/tm', headers={cert_pem_header: VALID_PEM})
    assert_response_header(response, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type=None)
