import os
import urllib.parse

import pytest
from httpx import AsyncClient
from psycopg import Connection

from envoy.server.main import generate_app
from envoy.admin.main import generate_app as admin_gen_app
from envoy.server.settings import generate_settings
from envoy.admin.settings import generate_settings as admin_gen_settings
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as VALID_PEM
from tests.integration.integration_server import cert_pem_header


@pytest.fixture
async def client(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the main server app"""

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = generate_app(generate_settings())
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest.fixture
def valid_headers():
    return {cert_pem_header: urllib.parse.quote(VALID_PEM)}


@pytest.fixture(scope="function")
async def admin_client_auth(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the main server app"""

    settings = admin_gen_settings()
    basic_auth = (settings.admin_username, settings.admin_password)

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = admin_gen_app(settings)
    async with AsyncClient(app=app, base_url="http://test", auth=basic_auth) as c:
        yield c
