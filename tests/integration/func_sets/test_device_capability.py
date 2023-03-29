from http import HTTPStatus

import pytest
from httpx import AsyncClient

from tests.integration.response import assert_response_header, read_response_body_string


@pytest.fixture
def uri():
    return "/dcap"


@pytest.mark.anyio
async def test_get_device_capability(client: AsyncClient, uri: str, headers: dict):
    """Simple test of a valid get - validates that the response looks like XML"""
    response = await client.get(uri, headers=headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0