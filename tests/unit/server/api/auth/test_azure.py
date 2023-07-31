import json
import unittest.mock as mock
from http import HTTPStatus

import jwt
import pytest
from httpx import Response

from envoy.server.api.auth.azure import (
    AzureADManagedIdentityConfig,
    UnableToContactAzureServicesError,
    clear_jwks_cache,
    parse_from_jwks_json,
    validate_azure_ad_token,
)
from envoy.server.api.auth.jwks import JWK
from envoy.server.exception import UnauthorizedError
from tests.unit.jwt import (
    DEFAULT_CLIENT_ID,
    DEFAULT_ISSUER,
    DEFAULT_TENANT_ID,
    TEST_KEY_1_PATH,
    TEST_KEY_2_PATH,
    generate_azure_jwk_definition,
    generate_kid,
    generate_rs256_jwt,
    load_rsa_pk,
)


@pytest.fixture
async def cache_reset() -> bool:
    """Fixture for resetting the cache between tests"""
    await clear_jwks_cache()


def test_parse_from_jwks_json():
    """Tests parsing a real world response"""
    with open("tests/data/azure/jwks-response.json") as f:
        json_response = json.loads(f.read())

    result_dict = parse_from_jwks_json(json_response["keys"])
    assert len(result_dict) == 6
    assert all([isinstance(v, JWK) for v in result_dict.values()])
    assert all([isinstance(k, str) for k in result_dict.keys()])
    assert len(set([v.rsa_modulus for v in result_dict.values()])) == len(
        result_dict
    ), "All modulus values should be distinct"
    assert len(set([v.pem_public for v in result_dict.values()])) == len(result_dict), "All PEM keys should be distinct"

    jwk = result_dict["DqUu8gf-nAgcyjP3-SuplNAXAnc"]
    assert jwk.key_type == "RSA"
    assert jwk.key_id == "DqUu8gf-nAgcyjP3-SuplNAXAnc"
    assert isinstance(jwk.rsa_exponent, int)
    assert jwk.rsa_exponent != 0
    assert isinstance(jwk.rsa_modulus, int)
    assert jwk.rsa_modulus != 0
    assert len(jwk.pem_public) != 0


def test_parse_from_filtered_jwks_json():
    """Tests parsing a response that requires filtering"""
    with open("tests/data/azure/jwks-response-filtered.json") as f:
        json_response = json.loads(f.read())

    result_dict = parse_from_jwks_json(json_response["keys"])
    assert len(result_dict) == 1

    jwk = result_dict["-KI3Q9nNR7bRofxmeZoXqbHZGew"]
    assert jwk.key_type == "RSA"
    assert jwk.key_id == "-KI3Q9nNR7bRofxmeZoXqbHZGew"
    assert isinstance(jwk.rsa_exponent, int)
    assert jwk.rsa_exponent != 0
    assert isinstance(jwk.rsa_modulus, int)
    assert jwk.rsa_modulus != 0
    assert len(jwk.pem_public) != 0


def generate_test_jwks_response(keys: list) -> str:
    return json.dumps({"keys": [generate_azure_jwk_definition(key) for key in keys]})


class MockedAsyncClient:
    """Looks similar to httpx AsyncClient() but returns a mocked response"""

    response: Response
    get_calls: int

    def __init__(self, response: Response) -> None:
        self.response = response
        self.get_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def get(self, uri):
        self.get_calls = self.get_calls + 1
        return self.response


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_token_full_token(mock_AsyncClient: mock.MagicMock, cache_reset):
    """Tests that a correctly signed Azure AD token validates and the jwk cache is operating"""

    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token1 = generate_rs256_jwt(key_file=TEST_KEY_1_PATH)
    token2 = generate_rs256_jwt(key_file=TEST_KEY_2_PATH)
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    pk2 = load_rsa_pk(TEST_KEY_2_PATH)
    raw_json_response = generate_test_jwks_response([pk2, pk1])

    # Mocking out the async client
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=raw_json_response))
    mock_AsyncClient.return_value = mocked_client

    await validate_azure_ad_token(cfg, token1)
    await validate_azure_ad_token(cfg, token2)
    await validate_azure_ad_token(cfg, token1)
    await validate_azure_ad_token(cfg, token2)

    assert mocked_client.get_calls == 1, "Cache should prevent further outgoing calls"


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_token_expired(mock_AsyncClient: mock.MagicMock, cache_reset):
    """Tests that expired/nbf are being validated"""
    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token1 = generate_rs256_jwt(key_file=TEST_KEY_1_PATH, expired=True)
    token2 = generate_rs256_jwt(key_file=TEST_KEY_2_PATH, premature=True)
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    pk2 = load_rsa_pk(TEST_KEY_2_PATH)
    raw_json_response = generate_test_jwks_response([pk1, pk2])

    # Mocking out the async client
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=raw_json_response))
    mock_AsyncClient.return_value = mocked_client

    with pytest.raises(jwt.ExpiredSignatureError):
        await validate_azure_ad_token(cfg, token1)
    with pytest.raises(jwt.ImmatureSignatureError):
        await validate_azure_ad_token(cfg, token2)

    assert mocked_client.get_calls == 1, "Cache should prevent further outgoing calls"


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_auth_server_inaccessible(mock_AsyncClient: mock.MagicMock, cache_reset):
    """Tests that the remote public key service being inaccessible kills validation"""

    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token1 = generate_rs256_jwt(key_file=TEST_KEY_1_PATH)
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    pk2 = load_rsa_pk(TEST_KEY_2_PATH)
    raw_json_response = generate_test_jwks_response([pk1, pk2])

    # Mocking out the async client
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.NOT_FOUND))
    mock_AsyncClient.return_value = mocked_client

    # Server is dead for the first/second call
    with pytest.raises(UnableToContactAzureServicesError):
        await validate_azure_ad_token(cfg, token1)
    with pytest.raises(UnableToContactAzureServicesError):
        await validate_azure_ad_token(cfg, token1)

    assert mocked_client.get_calls == 2, "Cache hasn't been populated yet"

    # But recovers fine for the third/fourth request
    mocked_client.response = Response(status_code=HTTPStatus.OK, content=raw_json_response)
    await validate_azure_ad_token(cfg, token1)
    await validate_azure_ad_token(cfg, token1)

    assert mocked_client.get_calls == 3, "Cache is now populated"


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_token_unrecognised_kid(mock_AsyncClient: mock.MagicMock, cache_reset):
    """Tests that an unrecognised key id will fail to validate"""

    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token1 = generate_rs256_jwt(key_file=TEST_KEY_1_PATH)  # Unrecognised kid
    token2 = generate_rs256_jwt(key_file=TEST_KEY_2_PATH)
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    pk2 = load_rsa_pk(TEST_KEY_2_PATH)
    raw_json_response = generate_test_jwks_response([pk2])

    # Mocking out the async client
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=raw_json_response))
    mock_AsyncClient.return_value = mocked_client

    # First token is unrecognised - second is fine
    with pytest.raises(UnauthorizedError):
        await validate_azure_ad_token(cfg, token1)
    await validate_azure_ad_token(cfg, token2)

    assert mocked_client.get_calls == 1, "Cache should prevent further outgoing calls"

    # Now update the response to include token1
    raw_json_response = generate_test_jwks_response([pk1, pk2])
    mocked_client.response = Response(status_code=HTTPStatus.OK, content=raw_json_response)
    await validate_azure_ad_token(cfg, token1)
    assert mocked_client.get_calls == 2, "The unrecognised token lookup triggers a cache update"


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_token_invalid_audience(mock_AsyncClient: mock.MagicMock, cache_reset):
    """Tests that a mismatching audience raises an error"""

    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token1 = generate_rs256_jwt(key_file=TEST_KEY_1_PATH, aud="new audience")
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    raw_json_response = generate_test_jwks_response([pk1])

    # Mocking out the async client
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=raw_json_response))
    mock_AsyncClient.return_value = mocked_client

    with pytest.raises(jwt.InvalidAudienceError):
        await validate_azure_ad_token(cfg, token1)

    assert mocked_client.get_calls == 1, "Cache should prevent further outgoing calls"


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_token_invalid_issuer(mock_AsyncClient: mock.MagicMock, cache_reset):
    """Tests that a mismatching issuer raises an error"""

    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token1 = generate_rs256_jwt(key_file=TEST_KEY_1_PATH, issuer="http://new.issuer/")
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    raw_json_response = generate_test_jwks_response([pk1])

    # Mocking out the async client
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=raw_json_response))
    mock_AsyncClient.return_value = mocked_client

    with pytest.raises(jwt.InvalidIssuerError):
        await validate_azure_ad_token(cfg, token1)

    assert mocked_client.get_calls == 1, "Cache should prevent further outgoing calls"


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_token_invalid_signature(mock_AsyncClient: mock.MagicMock, cache_reset):
    """Tests that a forged key id but invalid signature raises an error"""

    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token_valid = generate_rs256_jwt(key_file=TEST_KEY_1_PATH)
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    token_forged = generate_rs256_jwt(key_file=TEST_KEY_2_PATH, kid_override=generate_kid(pk1))
    raw_json_response = generate_test_jwks_response([pk1])

    # Mocking out the async client
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=raw_json_response))
    mock_AsyncClient.return_value = mocked_client

    await validate_azure_ad_token(cfg, token_valid)
    with pytest.raises(jwt.InvalidSignatureError):
        await validate_azure_ad_token(cfg, token_forged)

    assert mocked_client.get_calls == 1, "Cache should prevent further outgoing calls"
