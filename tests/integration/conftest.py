from collections import defaultdict

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from psycopg import Connection

from envoy.admin.main import generate_app as admin_gen_app
from envoy.admin.settings import generate_settings as admin_gen_settings
from envoy.server.main import generate_app
from envoy.server.settings import generate_settings
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as VALID_CERT_FINGERPRINT
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as VALID_CERT_PEM
from tests.integration.integration_server import cert_header
from tests.unit.jwt import generate_rs256_jwt


@pytest.fixture
async def client_empty_db(pg_empty_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the main server app (but the database
    will have no data in it)"""

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = generate_app(generate_settings())
    async with LifespanManager(app):  # This ensures that startup events are fired when the app starts
        async with AsyncClient(app=app, base_url="http://test") as c:
            yield c


@pytest.fixture
async def client(pg_base_config: Connection, client_empty_db):
    """Creates an AsyncClient for a test that is configured to talk to the main server app"""
    yield client_empty_db


@pytest.fixture
def valid_headers():
    return {cert_header: VALID_CERT_PEM.decode()}


@pytest.fixture
def valid_headers_fingerprint():
    return {cert_header: VALID_CERT_FINGERPRINT}


@pytest.fixture
def valid_headers_with_azure_ad():
    return {cert_header: VALID_CERT_FINGERPRINT, "Authorization": f"Bearer {generate_rs256_jwt()}"}


@pytest.fixture(scope="function")
async def admin_client_auth(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the main server app"""
    settings = admin_gen_settings()
    basic_auth = (settings.admin_username, settings.admin_password)

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = admin_gen_app(settings)
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test", auth=basic_auth) as c:
            yield c


@pytest.fixture(scope="function")
async def admin_client_unauth(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the main server app"""

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = admin_gen_app(admin_gen_settings())
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as c:
            yield c


@pytest.fixture(scope="session")
def admin_path_methods():
    app = admin_gen_app(admin_gen_settings())
    path_methods = defaultdict(list)
    for route in app.routes:
        path_methods[route.path] = path_methods[route.path] + list(route.methods)
    return path_methods
