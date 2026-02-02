import json
import unittest.mock as mock
from asyncio import sleep
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from assertical.fixtures.fastapi import start_app_with_client
from httpx import AsyncClient, Response
from psycopg import Connection
from sqlalchemy import event
from sqlalchemy.pool import Pool
from sqlalchemy.pool.base import _ConnectionRecord

from envoy.server.api.auth.azure import _PUBLIC_KEY_URI_FORMAT, _TOKEN_URI_FORMAT
from envoy.server.main import generate_app
from envoy.server.settings import generate_settings
from tests.integration.response import assert_response_header
from tests.unit.jwt import (
    DEFAULT_CLIENT_ID,
    DEFAULT_DATABASE_RESOURCE_ID,
    DEFAULT_TENANT_ID,
    TEST_KEY_1_PATH,
    load_rsa_pk,
)
from tests.unit.server.api.auth.test_azure import generate_test_jwks_response


def token_response(token: str, expires_in_seconds: int = 3600) -> str:
    return json.dumps(
        {
            "access_token": token,
            "client_id": DEFAULT_CLIENT_ID,
            "expires_in": str(expires_in_seconds),
            "expires_on": str(int((datetime.now() + timedelta(seconds=expires_in_seconds)).timestamp())),
            "resource": "https://ossrdbms-aad.database.windows.net",
            "token_type": "Bearer",
        }
    )


CUSTOM_DB_TOKEN = "my-custom-123database-token-{idx}"
TOKEN_URI = _TOKEN_URI_FORMAT.format(resource=DEFAULT_DATABASE_RESOURCE_ID, client_id=DEFAULT_CLIENT_ID)
JWK_URI = _PUBLIC_KEY_URI_FORMAT.format(tenant_id=DEFAULT_TENANT_ID)


@pytest.fixture
async def client_with_async_mock(pg_base_config: Connection):
    """Creates an AsyncClient for a test but installs mocks before generating the app so that
    the app startup can utilise these mocks

    The mocks will generate a unique database token every time they are called using CUSTOM_DB_TOKEN
    The mocks will use a fixed response for JWK_URI
    """
    with mock.patch("envoy.server.api.auth.azure.AsyncClient") as mock_AsyncClient:
        # Mocking out the async client to handle the JWK lookup (required for auth) and the Token lookup
        pk1 = load_rsa_pk(TEST_KEY_1_PATH)
        jwk_response_raw = generate_test_jwks_response([pk1])

        mocked_client = MockedAsyncClient(
            {
                # Generate a unique token every time the endpoint is called
                TOKEN_URI: [
                    Response(status_code=HTTPStatus.OK, content=token_response(CUSTOM_DB_TOKEN.format(idx=idx)))
                    for idx in range(10)
                ],
                JWK_URI: Response(status_code=HTTPStatus.OK, content=jwk_response_raw),
            }
        )
        mock_AsyncClient.return_value = mocked_client

        app = generate_app(generate_settings())
        async with start_app_with_client(app) as c:  # This ensures that startup events are fired when the app starts
            yield (c, mocked_client)


@pytest.mark.azure_ad_auth
@pytest.mark.azure_ad_db
@pytest.mark.anyio
async def test_enable_dynamic_azure_ad_database_credentials(
    client_with_async_mock: tuple[AsyncClient, MockedAsyncClient],
    valid_headers_with_azure_ad,
):
    """Heavily mocked / synthetic test that checks our usage of the SQLAlchemy core events that we use to inject
    dynamic credentials"""
    client, mocked_client = client_with_async_mock

    # Add a listener to capture DB connections
    db_connection_creds: list[tuple[str, str]] = []

    def on_db_connect(dbapi_connection, connection_record: _ConnectionRecord):
        """Pull out the password used to connect"""
        protocol = connection_record.driver_connection._protocol
        db_connection_creds.append((protocol.user, protocol.password))
        return

    event.listen(Pool, "connect", on_db_connect)

    try:
        # Now fire off a basic request to the time endpoint
        response = await client.request(
            method="GET",
            url="/tm",
            headers=valid_headers_with_azure_ad,
        )
        assert_response_header(response, HTTPStatus.OK)

        # Now validate that our db_token was used in the DB connection
        assert mocked_client.call_count_by_method[HTTPMethod.GET] == 2, "One call to JWK, one call to token lookup"
        assert mocked_client.call_count_by_method_uri[(HTTPMethod.GET, TOKEN_URI)] == 1
        assert mocked_client.call_count_by_method_uri[(HTTPMethod.GET, JWK_URI)] == 1

        # Lets dig into the guts of the current setup to pull out the db connections to see that
        # it includes our injected token
        assert len(db_connection_creds) == 1
        assert db_connection_creds[0][1] == CUSTOM_DB_TOKEN.format(
            idx=0
        ), "All attempts to access the DB should be using our CUSTOM_DB_TOKEN"
    finally:
        event.remove(Pool, "connect", on_db_connect)


@pytest.mark.azure_ad_auth
@pytest.mark.azure_ad_db
@pytest.mark.azure_ad_db_refresh_secs(1)
@pytest.mark.anyio
async def test_refresh_seconds_updating_cache(
    client_with_async_mock: tuple[AsyncClient, MockedAsyncClient],
    valid_headers_with_azure_ad,
):
    """Heavily mocked / synthetic test that validates the background task repeatedly updates the token cache on
    schedule (irrespective of errors). We use call outs to the token service as a proxy for the tokens being updated"""
    client, mocked_client = client_with_async_mock

    # Add a listener to capture DB connections
    db_connection_creds: list[tuple[str, str]] = []

    def on_db_connect(dbapi_connection, connection_record: _ConnectionRecord):
        """Pull out the password used to connect"""
        protocol = connection_record.driver_connection._protocol
        db_connection_creds.append((protocol.user, protocol.password))
        return

    event.listen(Pool, "connect", on_db_connect)

    # Now sit and do nothing for a period of time - this should allow a few tokens to cycle as we've set
    # the refresh rate to be 1/second
    await sleep(3.5)

    try:
        # Now fire off a basic request to the time endpoint
        response = await client.request(
            method="GET",
            url="/tm",
            headers=valid_headers_with_azure_ad,
        )
        assert_response_header(response, HTTPStatus.OK)

        # Now validate that our db_token was used in the DB connection

        token_requests = mocked_client.call_count_by_method_uri[(HTTPMethod.GET, TOKEN_URI)]
        jw_requests = mocked_client.call_count_by_method_uri[(HTTPMethod.GET, JWK_URI)]
        assert (
            token_requests >= 3 and token_requests <= 5
        ), "Depending on delays - should have 3 or 4 requests given the retry frequency and delay. +1 in case of load"
        assert jw_requests == 1

        # Lets dig into the guts of the current setup to pull out the db connections to see that
        # it includes our injected token
        # NOTE - this is very timing sensitive - the main part is ensuring that the token is changing
        assert len(db_connection_creds) == 1, "Only 1 DB connection was expected as we only make 1 request"
        assert db_connection_creds[0][1] in [
            CUSTOM_DB_TOKEN.format(idx=(token_requests - 1)),
            CUSTOM_DB_TOKEN.format(idx=(token_requests - 2)),
        ], "The CUSTOM_DB_TOKEN should match one of the latest minted tokens to indicate that it's changing"
        assert db_connection_creds[0][1] != CUSTOM_DB_TOKEN.format(idx=1), "Ensure its changing"
        assert db_connection_creds[0][1] != CUSTOM_DB_TOKEN.format(idx=0), "Ensure its changing"

    finally:
        event.remove(Pool, "connect", on_db_connect)
