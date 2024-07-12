import json
import unittest.mock as mock
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Optional
from urllib.parse import quote

import jwt
import pytest
from assertical.asserts.type import assert_dict_type
from assertical.fake.asyncio import create_async_result
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from httpx import Response

from envoy.server.api.auth.azure import (
    TOKEN_EXPIRY_BUFFER_SECONDS,
    AzureADManagedIdentityConfig,
    AzureADResourceTokenConfig,
    AzureADToken,
    UnableToContactAzureServicesError,
    parse_from_jwks_json,
    request_azure_ad_token,
    update_azure_ad_token_cache,
    update_jwk_cache,
    validate_azure_ad_token,
)
from envoy.server.api.auth.jwks import JWK
from envoy.server.cache import ExpiringValue
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

# cSpell: disable - No spell checking in this file due to a large number of b64 strings


def test_parse_from_jwks_json():
    """Tests parsing a real world response"""
    with open("tests/data/azure/jwks-response.json") as f:
        json_response = json.loads(f.read())

    result_dict = parse_from_jwks_json(json_response["keys"])
    assert len(result_dict) == 6
    assert all([isinstance(v, ExpiringValue) for v in result_dict.values()])
    assert all([isinstance(v.value, JWK) for v in result_dict.values()])
    assert all([v.expiry is None for v in result_dict.values()]), "Public keys dont explicitly expire"
    assert all([isinstance(k, str) for k in result_dict.keys()])
    assert len(set([v.value.rsa_modulus for v in result_dict.values()])) == len(
        result_dict
    ), "All modulus values should be distinct"
    assert len(set([v.value.pem_public for v in result_dict.values()])) == len(
        result_dict
    ), "All PEM keys should be distinct"

    expiring_val = result_dict["DqUu8gf-nAgcyjP3-SuplNAXAnc"]
    assert expiring_val.expiry is None, "Public keys dont explicitly expire"
    jwk = expiring_val.value
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

    expiring_val = result_dict["-KI3Q9nNR7bRofxmeZoXqbHZGew"]
    assert expiring_val.expiry is None, "Public keys dont explicitly expire"
    jwk = expiring_val.value
    assert jwk.key_type == "RSA"
    assert jwk.key_id == "-KI3Q9nNR7bRofxmeZoXqbHZGew"
    assert isinstance(jwk.rsa_exponent, int)
    assert jwk.rsa_exponent != 0
    assert isinstance(jwk.rsa_modulus, int)
    assert jwk.rsa_modulus != 0
    assert len(jwk.pem_public) != 0


def generate_test_jwks_response(keys: list) -> str:
    return json.dumps({"keys": [generate_azure_jwk_definition(key) for key in keys]})


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
@mock.patch("envoy.server.api.auth.azure.parse_from_jwks_json")
async def test_update_jwk_cache(mock_parse_from_jwks_json: mock.MagicMock, mock_AsyncClient: mock.MagicMock):
    # Arrange
    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    pk2 = load_rsa_pk(TEST_KEY_2_PATH)
    mocked_response_content = generate_test_jwks_response([pk2, pk1])
    mocked_parsed_response = {"abc": jwk_value_for_key(TEST_KEY_1_PATH)}

    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=mocked_response_content))
    mock_AsyncClient.return_value = mocked_client
    mock_parse_from_jwks_json.return_value = mocked_parsed_response

    # Act
    assert (await update_jwk_cache(cfg)) is mocked_parsed_response

    # Assert
    mock_parse_from_jwks_json.assert_called_once_with(
        [generate_azure_jwk_definition(pk2), generate_azure_jwk_definition(pk1)]
    )
    mocked_client.call_count_by_method[HTTPMethod.GET] == 1


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
@mock.patch("envoy.server.api.auth.azure.parse_from_jwks_json")
async def test_update_jwk_cache_http_error(mock_parse_from_jwks_json: mock.MagicMock, mock_AsyncClient: mock.MagicMock):
    """Tests that a HTTP 500 is remapped into a UnableToContactAzureServicesError"""
    # Arrange
    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)

    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR))
    mock_AsyncClient.return_value = mocked_client

    # Act
    with pytest.raises(UnableToContactAzureServicesError):
        await update_jwk_cache(cfg)

    # Assert
    mock_parse_from_jwks_json.assert_not_called()
    mocked_client.call_count_by_method[HTTPMethod.GET] == 1


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
@mock.patch("envoy.server.api.auth.azure.parse_from_jwks_json")
async def test_update_jwk_cache_exception(mock_parse_from_jwks_json: mock.MagicMock, mock_AsyncClient: mock.MagicMock):
    """Tests that an exception during get is remapped into a UnableToContactAzureServicesError"""
    # Arrange
    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)

    mocked_client = MockedAsyncClient(Exception("My Mocked Exception"))
    mock_AsyncClient.return_value = mocked_client

    # Act
    with pytest.raises(UnableToContactAzureServicesError):
        await update_jwk_cache(cfg)

    # Assert
    mock_parse_from_jwks_json.assert_not_called()
    mocked_client.call_count_by_method[HTTPMethod.GET] == 1


def jwk_value_for_key(key_file: str) -> JWK:
    pk = load_rsa_pk(key_file)
    jwk_defn = generate_azure_jwk_definition(pk)
    jwk_dict = parse_from_jwks_json([jwk_defn])
    return jwk_dict[generate_kid(pk)].value


class TokenContainer:
    """Silly workaround for pytest - having long tokens in params causes test discovery to go haywire
    Hiding it in an object where str(TokenContainer) is not 1KB of text works fine"""

    token: str

    def __init__(self, token: str) -> None:
        self.token = token


@pytest.mark.parametrize(
    "token, cache_result, expected_error, expected_kid",
    [
        # Everything is working OK
        (
            TokenContainer(generate_rs256_jwt(key_file=TEST_KEY_1_PATH)),
            jwk_value_for_key(TEST_KEY_1_PATH),
            None,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Expired token
        (
            TokenContainer(generate_rs256_jwt(key_file=TEST_KEY_1_PATH, expired=True)),
            jwk_value_for_key(TEST_KEY_1_PATH),
            jwt.ExpiredSignatureError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Premature token
        (
            TokenContainer(generate_rs256_jwt(key_file=TEST_KEY_1_PATH, premature=True)),
            jwk_value_for_key(TEST_KEY_1_PATH),
            jwt.ImmatureSignatureError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Unrecognised token
        (
            TokenContainer(generate_rs256_jwt(key_file=TEST_KEY_1_PATH)),
            None,
            UnauthorizedError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Invalid Audience
        (
            TokenContainer(generate_rs256_jwt(key_file=TEST_KEY_1_PATH, aud="invalid-audience")),
            jwk_value_for_key(TEST_KEY_1_PATH),
            jwt.InvalidAudienceError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Invalid Issuer
        (
            TokenContainer(generate_rs256_jwt(key_file=TEST_KEY_1_PATH, issuer="invalid-issuer")),
            jwk_value_for_key(TEST_KEY_1_PATH),
            jwt.InvalidIssuerError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Invalid Signature
        (
            TokenContainer(
                generate_rs256_jwt(key_file=TEST_KEY_1_PATH, kid_override=generate_kid(load_rsa_pk(TEST_KEY_2_PATH)))
            ),
            jwk_value_for_key(TEST_KEY_2_PATH),
            jwt.InvalidSignatureError,
            generate_kid(load_rsa_pk(TEST_KEY_2_PATH)),
        ),
    ],
)
@pytest.mark.anyio
async def test_validate_azure_ad_token(
    token: TokenContainer,
    cache_result: Optional[ExpiringValue[JWK]],
    expected_error: Optional[type],
    expected_kid: str,
):
    """Runs through all the ways we validate tokens to ensure the behaviour is valid for all the ways a token
    can be wrong"""

    # Arrange
    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    mock_cache = mock.Mock()
    mock_cache.get_value = mock.Mock(return_value=create_async_result(cache_result))

    # Act
    if expected_error:
        with pytest.raises(expected_error):
            await validate_azure_ad_token(cfg, mock_cache, token.token)
    else:
        await validate_azure_ad_token(cfg, mock_cache, token.token)

    # Assert
    mock_cache.get_value.assert_called_once_with(cfg, expected_kid)


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_request_azure_ad_token(mock_AsyncClient: mock.MagicMock):
    """Tests that the token response is parsed correctly"""

    # Arrange
    with open("tests/data/azure/token-response.json") as f:
        raw_token_response = f.read()
    resource_id = "resource id/&"  # with some chars that need escaping
    cfg = AzureADResourceTokenConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, resource_id)

    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=raw_token_response))
    mock_AsyncClient.return_value = mocked_client

    # Act
    output_token = await request_azure_ad_token(cfg)

    # Assert
    assert isinstance(output_token, AzureADToken)
    output_token.resource_id == resource_id
    output_token.token == "eyJ0eXAiOiJKV1Q...", "The value direct from the token-response.json"
    output_token.expiry == datetime.fromtimestamp(1690938812)
    mocked_client.call_count_by_method[HTTPMethod.GET] == 1

    assert mocked_client.logged_requests[0].headers == {"Metadata": "true"}
    assert quote(resource_id) in mocked_client.logged_requests[0].uri, "Resource ID should be included in request"
    assert quote(cfg.client_id) in mocked_client.logged_requests[0].uri, "Client ID should be included in request"


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_request_azure_ad_token_http_error(mock_AsyncClient: mock.MagicMock):
    """Tests that a HTTP error is reinterpreted as UnableToContactAzureServicesError"""

    # Arrange
    resource_id = "resource id"
    cfg = AzureADResourceTokenConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, resource_id)

    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR))
    mock_AsyncClient.return_value = mocked_client

    # Act
    with pytest.raises(UnableToContactAzureServicesError):
        await request_azure_ad_token(cfg)

    # Assert
    mocked_client.call_count_by_method[HTTPMethod.GET] == 1


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_request_azure_ad_token_exception(mock_AsyncClient: mock.MagicMock):
    """Tests that an exception is reinterpreted as UnableToContactAzureServicesError"""

    # Arrange
    resource_id = "resource id"
    cfg = AzureADResourceTokenConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, resource_id)

    mocked_client = MockedAsyncClient(Exception("My mocked error"))
    mock_AsyncClient.return_value = mocked_client

    # Act
    with pytest.raises(UnableToContactAzureServicesError):
        await request_azure_ad_token(cfg)

    # Assert
    mocked_client.call_count_by_method[HTTPMethod.GET] == 1


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.request_azure_ad_token")
async def test_update_azure_ad_token_cache(mock_request_azure_ad_token: mock.MagicMock):
    """Tests that the results of request_azure_ad_token are correctly packaged up into a dict"""

    # Arrange
    expected_token = AzureADToken("abc-123", "resource-456", datetime.now() + timedelta(hours=5))
    mock_request_azure_ad_token.return_value = expected_token
    cfg = AzureADResourceTokenConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, "my-resource-id")

    # Act
    token_cache = await update_azure_ad_token_cache(cfg)

    # Assert
    mock_request_azure_ad_token.assert_called_once_with(cfg)
    assert_dict_type(str, ExpiringValue, token_cache, count=1)

    expiring_val = token_cache["my-resource-id"]
    assert isinstance(expiring_val, ExpiringValue)
    assert expiring_val.value == expected_token.token
    assert expiring_val.expiry == (
        expected_token.expiry + timedelta(seconds=-TOKEN_EXPIRY_BUFFER_SECONDS)
    ), "Expiry buffer should be applied"
