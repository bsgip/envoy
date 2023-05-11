import re
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient

from tests.integration.http import HTTPMethod
from tests.integration.response import assert_response_header, read_response_body_string, run_basic_unauthorised_tests

EMPTY_XML_DOC = '<?xml version="1.0" encoding="UTF-8"?>\n<tag/>'


# All of our endpoints with their supported method types
# fmt: off
ALL_ENDPOINTS_WITH_SUPPORTED_METHODS: list[tuple[list[HTTPMethod], str]] = [
    # time function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tm"),

    # device capability function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/dcap"),

    # edev function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD, HTTPMethod.POST], "/edev"),
    ([HTTPMethod.GET, HTTPMethod.HEAD, HTTPMethod.POST, HTTPMethod.PUT], "/edev/1/cp"),

    # function-set-assignments function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/fsa"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/fsa/1"),

    # Pricing function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/pricing/rt/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1"),  # Tariff - no site scoping
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/tp/1/rc"),  # Tariff - no site scoping
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp/1/rc"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp/1/rc/2022-03-05/1"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp/1/rc/2022-03-05/1/tti"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp/1/rc/2022-03-05/1/tti/01%3A02"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp/1/rc/2022-03-05/1/tti/01%3A02/cti/100"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/tp/1/rc/2022-03-05/1/tti/01%3A02/cti/100/1"),

    # derp/derc function set
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/derp"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/derp/doe"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/derp/doe/derc"),
    ([HTTPMethod.GET, HTTPMethod.HEAD], "/edev/1/derp/doe/derc/2022-05-07"),
]
# fmt: on


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
async def test_resource_with_invalid_methods(
    valid_methods: list[HTTPMethod], uri: str, client: AsyncClient, valid_headers: dict
):
    """Runs through invalid HTTP methods for each endpoint"""
    for method in [m for m in HTTPMethod if m not in valid_methods]:
        body: Optional[str] = None
        if method != HTTPMethod.GET and method != HTTPMethod.HEAD:
            body = EMPTY_XML_DOC

        response = await client.request(method=method.name, url=uri, content=body, headers=valid_headers)
        assert_response_header(response, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type=None)


@pytest.mark.anyio
async def test_crawl_hrefs(client: AsyncClient, valid_headers: dict):
    """Crawls through ALL_ENDPOINTS_WITH_SUPPORTED_METHODS - makes every get request
    and trawls the responses looking for more hrefs. the idea is to ensure that every sequence
    of hrefs point to valid endpoints within envoy"""
    uris_to_visit = [
        (uri, "initial") for (methods, uri) in ALL_ENDPOINTS_WITH_SUPPORTED_METHODS if HTTPMethod.GET in methods
    ]
    visited_uris: set[str] = set()
    href_extractor = re.compile('href[\\r\\n ]*=[\\r\\n ]*"([^"]*)"', re.MULTILINE | re.IGNORECASE)

    while len(uris_to_visit) > 0:
        # get the next URI to visit
        (uri, src_uri) = uris_to_visit.pop()
        if uri in visited_uris:
            continue
        visited_uris.add(uri)

        # make the request
        response = await client.get(uri, headers=valid_headers)
        if response.status_code == HTTPStatus.NOT_FOUND:
            assert False, f"URI {uri} is not found. It was sourced from {src_uri}"
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0, f"Empty body for {uri}"

        # search for more hrefs to request from our response
        for match in re.finditer(href_extractor, body):
            new_uri = match.group(1)
            if new_uri not in visited_uris:
                uris_to_visit.append((new_uri, uri))
    assert len(visited_uris) > len(ALL_ENDPOINTS_WITH_SUPPORTED_METHODS), "Sanity check to ensure we are finding uris"
