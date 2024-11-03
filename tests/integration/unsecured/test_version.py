from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.server.api.unsecured.version import VERSION_URI
from tests.integration.response import read_response_body_string


@pytest.mark.anyio
async def test_get_version_works_for_any_auth(client: AsyncClient, valid_headers):
    """Checks HEALTH_URI returns HTTP 200 for all requests (ignoring auth)"""

    # no login
    response = await client.request(method="GET", url=VERSION_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"

    # valid login
    response = await client.request(method="GET", url=VERSION_URI, headers=valid_headers)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_version_returns_semver(client: AsyncClient):
    """Checks the health check will fail if the DB is empty"""

    response = await client.request(method="GET", url=VERSION_URI)
    assert response.status_code == HTTPStatus.OK
    response_body = read_response_body_string(response)

    version_parts = [int(p) for p in response_body.split(".")]
    assert len(version_parts) == 3
    assert version_parts != [0, 0, 0]
