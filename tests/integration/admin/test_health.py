from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.admin.api.health import HEALTH_URI
from tests.integration.response import read_response_body_string


@pytest.mark.anyio
async def test_get_health_unauth(admin_client_unauth: AsyncClient):
    """Checks HEALTH_URI returns HTTP 200 for all requests (ignoring auth)"""

    response = await admin_client_unauth.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_health_auth(admin_client_auth: AsyncClient):
    """Checks HEALTH_URI returns HTTP 200 for all requests (with auth)"""

    response = await admin_client_auth.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_health_readonly_auth(admin_client_readonly_auth: AsyncClient):
    """Checks HEALTH_URI returns HTTP 200 for all requests (with readonly auth)"""

    response = await admin_client_readonly_auth.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_health_detects_no_data(admin_client_empty_db: AsyncClient):
    """Checks the health check will fail if the DB is empty"""

    response = await admin_client_empty_db.request(method="GET", url=HEALTH_URI)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert read_response_body_string(response), "Expected a response with some content"


@pytest.mark.anyio
async def test_get_health_detects_no_data_not_checking(admin_client_empty_db: AsyncClient):
    """Checks the health check will pass if the DB is empty and we aren't checking for data"""

    response = await admin_client_empty_db.request(method="GET", url=HEALTH_URI + "?check_data=false")
    assert response.status_code == HTTPStatus.OK
    assert read_response_body_string(response), "Expected a response with some content"
