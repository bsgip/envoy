from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.server.schema import uri
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse
from tests.integration.response import assert_response_header, read_response_body_string


@pytest.mark.anyio
async def test_get_device_capability(client: AsyncClient, valid_headers: dict):
    """Simple test of a valid get - validates that the response looks like XML"""
    response = await client.get(uri.DeviceCapabilityUri, headers=valid_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DeviceCapabilityResponse = DeviceCapabilityResponse.from_xml(body)
    assert parsed_response.href == uri.DeviceCapabilityUri
