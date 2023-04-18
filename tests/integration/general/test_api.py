from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient

from tests.integration.http import HTTPMethod
from tests.integration.response import assert_response_header, run_basic_unauthorised_tests

EMPTY_XML_DOC = '<?xml version="1.0" encoding="UTF-8"?>\n<tag/>'

# All of our endpoints with their supported method types
ALL_ENDPOINTS_WITH_SUPPORTED_METHODS: list[tuple[list[HTTPMethod], str]] = [
    # time function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tm"),

    # edev function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD, HTTPMethod.POST], "/edev"),
    ([HTTPMethod.GET, HTTPMethod.HEAD, HTTPMethod.POST, HTTPMethod.PUT], "/edev/1/cp"),

    # Pricing function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/pricing/rt/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/rc"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/1/rc"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/1/rc/2022-01-02/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/1/rc/2022-01-02/1/tti"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/1/rc/2022-01-02/1/tti/01%3A02"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/1/rc/2022-01-02/1/tti/01%3A02/cti"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/1/rc/2022-01-02/1/tti/01%3A02/cti/100"),
]

@pytest.mark.parametrize("valid_methods,uri", ALL_ENDPOINTS_WITH_SUPPORTED_METHODS)
@pytest.mark.anyio
async def test_get_resource_unauthorised(valid_methods: list[HTTPMethod], uri: str, client: AsyncClient):
    """Runs through the basic unauthorised tests for all parametized requests"""
    for method in valid_methods:
        body: Optional[str] = None
        if method != HTTPMethod.GET and method != HTTPMethod.HEAD:
            body = EMPTY_XML_DOC

        await run_basic_unauthorised_tests(client, uri, method=method.name, body=body)


@pytest.mark.parametrize("valid_methods,uri", ALL_ENDPOINTS_WITH_SUPPORTED_METHODS)
@pytest.mark.anyio
async def test_resource_with_invalid_methods(valid_methods: list[HTTPMethod], uri: str,
                                             client: AsyncClient, valid_headers: dict):
    """Runs through invalid HTTP methods for each endpoint"""
    for method in [m for m in HTTPMethod if m not in valid_methods]:
        body: Optional[str] = None
        if method != HTTPMethod.GET and method != HTTPMethod.HEAD:
            body = EMPTY_XML_DOC

        response = await client.request(method=method.name, url=uri, content=body, headers=valid_headers)
        assert_response_header(response, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type=None)
