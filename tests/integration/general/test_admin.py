import re
from collections import defaultdict
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.admin.api.health import HEALTH_URI
from tests.integration.http import HTTPMethod
from tests.integration.response import assert_response_header

NO_AUTH_ROUTES = ["/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", HEALTH_URI]


@pytest.mark.anyio
async def test_get_resource_unauthorised(
    admin_client_unauth: AsyncClient, admin_path_methods: defaultdict[str, list[str]]
):
    """Runs through the basic unauthorised tests across all routes"""
    routes = admin_path_methods
    client = admin_client_unauth

    for path, methods in routes.items():
        if path not in NO_AUTH_ROUTES:
            for method in methods:
                resp = await client.request(method=method, url=path)

                assert_response_header(resp, HTTPStatus.UNAUTHORIZED, expected_content_type="application/json")


@pytest.mark.anyio
async def test_resource_with_invalid_methods(
    admin_client_auth: AsyncClient, admin_path_methods: defaultdict[str, list[str]]
):
    """Runs through invalid HTTP methods for each endpoint"""
    routes = admin_path_methods
    client = admin_client_auth

    for path, methods in routes.items():
        for method in [m for m in HTTPMethod if m.name not in methods]:
            resp = await client.request(method=method.name, url=path)
            assert_response_header(resp, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type="application/json")


def infill_path_format_variables(path_format: str) -> str:
    """Given a format like '/doe/{doe_id}' tries to guess and infill the parameters to return '/doe/1'. Tries
    to be as clever as possible"""
    pattern = r"\{([^\}]*)\}"
    kvps = {}
    for format_var_name in re.findall(pattern, path_format):
        infill_value = 1
        if "group" in format_var_name:
            if "site_control_group" in path_format:
                infill_value = 1
            else:
                infill_value = "Group-1"
        elif "start" in format_var_name or "end" in format_var_name:
            infill_value = "2024-01-02T03:04:05Z"

        kvps[format_var_name] = infill_value

    return path_format.format(**kvps)


@pytest.mark.anyio
@pytest.mark.admin_ro_user
async def test_readonly_client_can_only_access_get(
    admin_client_readonly_auth: AsyncClient, admin_path_methods: dict[list]
):
    """Enumerates admin endpoints (that are protected) and ensures that the GET endpoints allow access but other methods
    are locked down"""
    for path, methods in admin_path_methods.items():
        if path in NO_AUTH_ROUTES:
            continue

        for method in [m for m in HTTPMethod if m.name in methods]:
            resp = await admin_client_readonly_auth.request(method=method.name, url=infill_path_format_variables(path))
            if method == HTTPMethod.GET:
                assert_response_header(resp, HTTPStatus.OK, expected_content_type="application/json")
            else:
                assert_response_header(resp, HTTPStatus.FORBIDDEN, expected_content_type="application/json")


@pytest.mark.anyio
async def test_readonly_client_not_installed(admin_client_readonly_auth: AsyncClient, admin_path_methods: dict[list]):
    """Similar to test_readonly_client_can_only_access_get but with a bad set of credentials"""
    for path, methods in admin_path_methods.items():
        if path in NO_AUTH_ROUTES:
            continue

        for method in [m for m in HTTPMethod if m.name in methods]:
            resp = await admin_client_readonly_auth.request(method=method.name, url=infill_path_format_variables(path))
            assert_response_header(resp, HTTPStatus.UNAUTHORIZED, expected_content_type="application/json")
