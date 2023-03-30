from http import HTTPStatus

import pytest
from httpx import AsyncClient

from tests.integration.http import HTTPMethod
from tests.integration.response import assert_response_header, run_basic_unauthorised_tests


@pytest.mark.parametrize(
    "uri",
    ["/tm"],
)
@pytest.mark.anyio
async def test_get_resource_unauthorised(uri: str, client: AsyncClient):
    await run_basic_unauthorised_tests(client, uri, method="GET")


@pytest.mark.parametrize(
    "uri,invalid_methods",
    [
        ("/tm", [HTTPMethod.PUT, HTTPMethod.DELETE, HTTPMethod.POST]),
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
