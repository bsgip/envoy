from http import HTTPStatus
from typing import Any, Optional

import pytest
from httpx import AsyncClient

from tests.integration.http import HTTPMethod
from tests.integration.response import assert_response_header, run_basic_unauthorised_tests

EMPTY_XML_DOC = '<?xml version="1.0" encoding="UTF-8"?>\n<tag/>'

EMPTY_XML_DOC = '<?xml version="1.0" encoding="UTF-8"?>\n<tag/>'


@pytest.mark.parametrize(
    "request_content",
    [(["GET"], "/tm", None),
     (["GET", "HEAD"], "/edev/1", None),
     (["GET", "HEAD"], "/edev", None),
     (["POST"], "/edev", EMPTY_XML_DOC),
     (["GET", "HEAD"], "/edev/1/cp", None),
     (["POST", "PUT"], "/edev/1/cp", EMPTY_XML_DOC)]
)
@pytest.mark.anyio
async def test_get_resource_unauthorised(request_content: tuple[list[str], str, Optional[Any]], client: AsyncClient):
    """Runs through the basic unauthorised tests for all parametized requests"""
    (methods, uri, body) = request_content
    for method in methods:
        await run_basic_unauthorised_tests(client, uri, method=method, body=body)


@pytest.mark.parametrize(
    "uri,invalid_methods",
    [
        ("/tm", [HTTPMethod.PUT, HTTPMethod.DELETE, HTTPMethod.POST, HTTPMethod.PATCH]),
        ("/edev/1", [HTTPMethod.PUT, HTTPMethod.POST, HTTPMethod.PATCH]),
        ("/edev", [HTTPMethod.PATCH, HTTPMethod.DELETE]),
        ("/edev/1/cp", [HTTPMethod.PATCH, HTTPMethod.DELETE]),
    ],
)
@pytest.mark.anyio
async def test_resource_with_invalid_methods(
    uri: str, invalid_methods: list[HTTPMethod], client: AsyncClient, valid_headers: dict
):
    http_method_to_client_function_mapping = {
        HTTPMethod.DELETE: client.delete,
        HTTPMethod.GET: client.get,
        HTTPMethod.HEAD: client.head,
        HTTPMethod.POST: client.post,
        HTTPMethod.PATCH: client.patch,
        HTTPMethod.PUT: client.put,
    }
    for http_method in invalid_methods:
        client_function = http_method_to_client_function_mapping[http_method]
        response = await client_function(uri, headers=valid_headers)
        assert_response_header(response, HTTPStatus.METHOD_NOT_ALLOWED, expected_content_type=None)
