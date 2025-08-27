import unittest.mock as mock
from collections import defaultdict
from http import HTTPStatus
from typing import AsyncGenerator

import pytest
from assertical.fake.http import MockedAsyncClient
from assertical.fixtures.fastapi import start_app_with_client
from httpx import Response
from psycopg import Connection

from envoy.admin.main import generate_app as admin_gen_app
from envoy.admin.settings import generate_settings as admin_gen_settings
from envoy.server.main import generate_app
from envoy.server.settings import generate_settings
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as VALID_CERT_FINGERPRINT
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as VALID_CERT_PEM
from tests.integration.integration_server import cert_header
from tests.integration.notification import TestableBroker
from tests.unit.jwt import generate_rs256_jwt

READONLY_USER_NAME = "mycustomrouser"
READONLY_USER_KEY_1 = "my_custom+!@#$23key1"  # Fake password for testing readonly user
READONLY_USER_KEY_2 = "another_custom+!@#$23key2"  # Fake password for testing readonly user


@pytest.fixture
async def client_empty_db(pg_empty_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the main server app (but the database
    will have no data in it)"""

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = generate_app(generate_settings())
    async with start_app_with_client(app) as c:
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
async def admin_client_empty_db(pg_empty_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the admin server app (base config not loaded)"""
    settings = admin_gen_settings()
    basic_auth = (settings.admin_username, settings.admin_password)

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = admin_gen_app(settings)
    async with start_app_with_client(app, client_auth=basic_auth) as c:
        yield c


@pytest.fixture(scope="function")
async def admin_client_auth(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the admin server app"""
    settings = admin_gen_settings()
    basic_auth = (settings.admin_username, settings.admin_password)

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = admin_gen_app(settings)
    async with start_app_with_client(app, client_auth=basic_auth) as c:
        yield c


@pytest.fixture(scope="function")
async def admin_client_readonly_auth(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the admin server app that will authenticate
    with the READONLY_USER_NAME/READONLY_USER_KEY_2 combo"""
    settings = admin_gen_settings()
    basic_auth = (READONLY_USER_NAME, READONLY_USER_KEY_2)

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = admin_gen_app(settings)
    async with start_app_with_client(app, client_auth=basic_auth) as c:
        yield c


@pytest.fixture(scope="function")
async def admin_client_unauth(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the admin server app that doesn't
    have any authentication installed"""

    # We want a new app instance for every test - otherwise connection pools get shared and we hit problems
    # when trying to run multiple tests sequentially
    app = admin_gen_app(admin_gen_settings())
    async with start_app_with_client(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_path_methods() -> defaultdict[str, list[str]]:
    app = admin_gen_app(admin_gen_settings())
    path_methods = defaultdict(list)
    for route in app.routes:
        path_methods[route.path] = path_methods[route.path] + list(route.methods)
    return path_methods


@pytest.fixture(scope="function")
async def notifications_enabled(
    pg_empty_config, request: pytest.FixtureRequest
) -> AsyncGenerator[MockedAsyncClient, None]:
    """Enables notifications for the server and returns a MockedAsyncClient which
    will be patched to receive all outgoing notification POST requests.

    The returned client will default to always returning HTTP NO_CONTENT on get/post"""

    # We need to inject our own extension to the TaskIQ in memory broker that's configured
    # with the appropriate state
    href_prefix_marker = request.node.get_closest_marker("href_prefix")
    if href_prefix_marker is not None:
        href_prefix = str(href_prefix_marker.args[0])
    else:
        href_prefix = None
    broker = TestableBroker(pg_empty_config, href_prefix)

    mock_async_client = MockedAsyncClient(Response(status_code=HTTPStatus.NO_CONTENT))
    with mock.patch("envoy.notification.task.transmit.AsyncClient") as mock_AsyncClient:
        mock_AsyncClient.return_value = mock_async_client
        with mock.patch("envoy.notification.manager.notification.get_enabled_broker") as mock_get_enabled_broker:
            await broker.startup()
            mock_get_enabled_broker.return_value = broker

            yield mock_async_client

            await broker.shutdown()
