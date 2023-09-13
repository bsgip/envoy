from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.server.api.unsecured.health import HEALTH_URI
from tests.integration.response import read_response_body_string


@pytest.mark.anyio
async def test_get_health_works_for_any_auth(client: AsyncClient, valid_headers):
    """Checks HEALTH_URI returns HTTP 200 for all requests (ignoring auth)"""

    # no login
    response = await client.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"

    # valid login
    response = await client.request(method="GET", url=HEALTH_URI, headers=valid_headers)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_health_detects_no_data(client_empty_db: AsyncClient):
    """Checks the health check will fail if the DB is empty"""

    response = await client_empty_db.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert read_response_body_string(response), "Expected a response with some content"
