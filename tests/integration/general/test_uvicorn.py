import urllib
from typing import AsyncGenerator
from itertools import product

import pytest
from assertical.fixtures.fastapi import start_uvicorn_server
from httpx import AsyncClient

from envoy.server.api.depends.csipaus import CSIPV11aXmlNsOptInMiddleware
from envoy.server.main import generate_app
from envoy.server.settings import generate_settings

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.integration.integration_server import cert_header
from tests.integration.general.test_api import ALL_ENDPOINTS_WITH_SUPPORTED_METHODS
from tests.integration.http import HTTPMethod


@pytest.fixture(scope="function")
async def running_uvicorn(pg_base_config) -> AsyncGenerator[str, None]:
    settings = generate_settings()
    app = generate_app(settings)
    async with start_uvicorn_server(app) as base_uri:
        yield base_uri


@pytest.mark.parametrize(
    "opt_in, get_uri",
    product([True, False], [uri for methods, uri in ALL_ENDPOINTS_WITH_SUPPORTED_METHODS if HTTPMethod.GET in methods]),
)
@pytest.mark.csipv11a_xmlns_optin_middleware
@pytest.mark.anyio
async def test_run_with_full_stack(running_uvicorn, opt_in, get_uri):

    client = AsyncClient()

    headers = {
        cert_header: urllib.parse.quote(AGG_1_VALID_CERT),
    }
    if opt_in:
        headers[CSIPV11aXmlNsOptInMiddleware.opt_in_header_name] = ""

    response = await client.get(running_uvicorn + get_uri, headers=headers)
    data = response.content.decode()
    assert response.status_code == 200, data
