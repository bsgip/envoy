import json
import unittest.mock as mock
from asyncio import sleep
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient, Response
from psycopg import Connection
from sqlalchemy import event
from sqlalchemy.pool import Pool
from sqlalchemy.pool.base import _ConnectionRecord

from envoy.server.api.auth.azure import _PUBLIC_KEY_URI_FORMAT, _TOKEN_URI_FORMAT
from envoy.server.main import generate_app
from envoy.server.settings import generate_settings
from tests.integration.response import assert_response_header
from tests.postgres_testing import generate_async_conn_str_from_connection
from tests.unit.jwt import (
    DEFAULT_CLIENT_ID,
    DEFAULT_DATABASE_RESOURCE_ID,
    DEFAULT_TENANT_ID,
    TEST_KEY_1_PATH,
    load_rsa_pk,
)
from tests.unit.mocks import MockedAsyncClient
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


CUSTOM_DB_TOKEN = "my-custom-123database-token"


@pytest.fixture
async def client_with_async_mock(pg_base_config: Connection):
    """Creates an AsyncClient for a test but installs mocks before generating the app so that
    the app startup can utilise these mocks"""
    with mock.patch("envoy.server.api.auth.azure.AsyncClient") as mock_AsyncClient:
        token_uri = _TOKEN_URI_FORMAT.format(resource=DEFAULT_DATABASE_RESOURCE_ID, client_id=DEFAULT_CLIENT_ID)
        jwk_uri = _PUBLIC_KEY_URI_FORMAT.format(tenant_id=DEFAULT_TENANT_ID)

        # Mocking out the async client to handle the JWK lookup (required for auth) and the Token lookup
        pk1 = load_rsa_pk(TEST_KEY_1_PATH)
        jwk_response_raw = generate_test_jwks_response([pk1])
        token_response_raw = token_response(CUSTOM_DB_TOKEN)

        mocked_client = MockedAsyncClient(
            {
                token_uri: Response(status_code=HTTPStatus.OK, content=token_response_raw),
                jwk_uri: Response(status_code=HTTPStatus.OK, content=jwk_response_raw),
            }
        )
        mock_AsyncClient.return_value = mocked_client

        app = generate_app(generate_settings())
        async with AsyncClient(app=app, base_url="http://test") as c:
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
    (client, mocked_client) = client_with_async_mock

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
        assert mocked_client.get_calls == 2, "One call to JWK, one call to token lookup"

        # Lets dig into the guts of the current setup to pull out the db connections to see that
        # it includes our injected token
        assert len(db_connection_creds) > 0
        assert all(
            [pwd == CUSTOM_DB_TOKEN for (_, pwd) in db_connection_creds]
        ), "All attempts to access the DB should be using our CUSTOM_DB_TOKEN"
    finally:
        event.remove(Pool, "connect", on_db_connect)
