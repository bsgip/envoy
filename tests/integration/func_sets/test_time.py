from datetime import datetime
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.server.schema.sep2.time import TimeResponse
from tests.integration.response import assert_response_header, read_response_body_string


@pytest.fixture
def uri():
    return "/tm"


@pytest.mark.anyio
async def test_get_time_resource(client: AsyncClient, uri: str, valid_headers: dict):
    """Simple test of a valid get - validates that the response looks like XML"""
    response = await client.get(uri, headers=valid_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TimeResponse = TimeResponse.from_xml(body)

    diff = datetime.now().timestamp() - parsed_response.currentTime
    assert diff > 0 and diff < 20, f"Diff between now and the timestamp value is {diff}. Was expected to be small"
    assert parsed_response.quality == 4
