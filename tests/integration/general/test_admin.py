import pytest
from http import HTTPStatus
from httpx import AsyncClient

from tests.integration.http import HTTPMethod
from tests.integration.response import assert_response_header

NO_AUTH_ROUTES = ["/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"]


@pytest.mark.anyio
async def test_get_resource_unauthorised(admin_client_unauth: AsyncClient, admin_path_methods: dict[list]):
    """Runs through the basic unauthorised tests across all routes"""
    routes = admin_path_methods
    client = admin_client_unauth

    for path, methods in routes.items():
        if path not in NO_AUTH_ROUTES:
            for method in methods:
                resp = await client.request(method=method, url=path)

                assert_response_header(resp, HTTPStatus.UNAUTHORIZED, expected_content_type="application/json")


@pytest.mark.anyio
async def test_resource_with_invalid_methods(admin_client_auth: AsyncClient, admin_path_methods: dict[list]):
    """Runs through invalid HTTP methods for each endpoint"""
    routes = admin_path_methods
    client = admin_client_auth

    for path, methods in routes.items():
        for method in [m for m in HTTPMethod if m.name not in methods]:
            resp = await client.request(method=method.name, url=path)
            assert_response_header(resp, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type="application/json")
