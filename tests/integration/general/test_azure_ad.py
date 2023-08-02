import json
import unittest.mock as mock
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient, Response

from envoy.server.api.auth.azure import _PUBLIC_KEY_URI_FORMAT, _TOKEN_URI_FORMAT
from tests.integration.response import assert_response_header
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


@pytest.mark.azure_ad_auth
@pytest.mark.azure_ad_db
@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_enable_dynamic_azure_ad_database_credentials(
    mock_AsyncClient: mock.MagicMock,
    client: AsyncClient,
    valid_headers_with_azure_ad,
):
    """Heavily mocked / synthetic test that checks our usage of the SQLAlchemy core events that we use to inject
    dynamic credentials"""

    token_uri = _TOKEN_URI_FORMAT.format(resource=DEFAULT_DATABASE_RESOURCE_ID, client_id=DEFAULT_CLIENT_ID)
    jwk_uri = _PUBLIC_KEY_URI_FORMAT.format(tenant_id=DEFAULT_TENANT_ID)

    # Mocking out the async client to handle the JWK lookup (required for auth) and the Token lookup
    db_token = "my-custom-database-token"
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    jwk_response_raw = generate_test_jwks_response([pk1])
    token_response_raw = token_response(db_token)

    mocked_client = MockedAsyncClient(
        {
            token_uri: Response(status_code=HTTPStatus.OK, content=token_response_raw),
            jwk_uri: Response(status_code=HTTPStatus.OK, content=jwk_response_raw),
        }
    )
    mock_AsyncClient.return_value = mocked_client

    # Now fire off a basic request to the time endpoint
    response = await client.request(
        method="GET",
        url="/tm",
        headers=valid_headers_with_azure_ad,
    )
    assert_response_header(response, HTTPStatus.OK)

    # Now validate that our db_token was used in the DB connection
    raise Exception("not implemented")
