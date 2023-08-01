import json
import unittest.mock as mock
from http import HTTPStatus
from typing import Optional, Union

import jwt
import pytest
from httpx import Response

from envoy.server.api.auth.azure import (
    AzureADManagedIdentityConfig,
    UnableToContactAzureServicesError,
    parse_from_jwks_json,
    update_jwk_cache,
    validate_azure_ad_token,
)
from envoy.server.api.auth.jwks import JWK
from envoy.server.cache import AsyncCache, ExpiringValue
from envoy.server.exception import UnauthorizedError
from tests.data.fake.generator import generate_class_instance
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
    assert len(set([v.rsa_modulus for v in result_dict.values()])) == len(
        result_dict
    ), "All modulus values should be distinct"
    assert len(set([v.pem_public for v in result_dict.values()])) == len(result_dict), "All PEM keys should be distinct"

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


class MockedAsyncClient:
    """Looks similar to httpx AsyncClient() but returns a mocked response"""

    response: Optional[Response]
    get_calls: int
    error_to_raise: Optional[Exception]

    def __init__(self, result: Union[Response, Exception]) -> None:
        if isinstance(result, Response):
            self.response = result
            self.error_to_raise = None
        else:
            self.response = None
            self.error_to_raise = result

        self.get_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def get(self, uri):
        self.get_calls = self.get_calls + 1
        if self.error_to_raise:
            raise self.error_to_raise

        return self.response


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
@mock.patch("envoy.server.api.auth.azure.parse_from_jwks_json")
async def test_update_jwk_cache(mock_parse_from_jwks_json: mock.MagicMock, mock_AsyncClient: mock.MagicMock):
    # Arrange
    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    pk1 = load_rsa_pk(TEST_KEY_1_PATH)
    pk2 = load_rsa_pk(TEST_KEY_2_PATH)
    mocked_response_content = generate_test_jwks_response([pk2, pk1])
    mocked_parsed_response = {"abc": ExpiringValue(None, generate_class_instance(JWK))}

    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content=mocked_response_content))
    mock_AsyncClient.return_value = mocked_client
    mock_parse_from_jwks_json.return_value = mocked_parsed_response

    # Act
    assert (await update_jwk_cache(cfg)) is mocked_parsed_response

    # Assert
    mock_parse_from_jwks_json.assert_called_once_with(
        [generate_azure_jwk_definition(pk2), generate_azure_jwk_definition(pk1)]
    )
    mocked_client.get_calls == 1


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
    mocked_client.get_calls == 1


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
    mocked_client.get_calls == 1


def expiring_value_for_key(key_file: str) -> ExpiringValue[JWK]:
    pk = load_rsa_pk(key_file)
    jwk_defn = generate_azure_jwk_definition(pk)
    jwk_dict = parse_from_jwks_json([jwk_defn])
    return jwk_dict[generate_kid(pk)]


@pytest.mark.parametrize(
    "token, cache_result, expected_error, expected_kid",
    [
        # Everything is working OK
        (
            generate_rs256_jwt(key_file=TEST_KEY_1_PATH),
            expiring_value_for_key(TEST_KEY_1_PATH),
            None,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Expired token
        (
            generate_rs256_jwt(key_file=TEST_KEY_1_PATH, expired=True),
            expiring_value_for_key(TEST_KEY_1_PATH),
            jwt.ExpiredSignatureError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Premature token
        (
            generate_rs256_jwt(key_file=TEST_KEY_1_PATH, premature=True),
            expiring_value_for_key(TEST_KEY_1_PATH),
            jwt.ImmatureSignatureError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Unrecognised token
        (
            generate_rs256_jwt(key_file=TEST_KEY_1_PATH),
            None,
            UnauthorizedError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Invalid Audience
        (
            generate_rs256_jwt(key_file=TEST_KEY_1_PATH, aud="invalid-audience"),
            expiring_value_for_key(TEST_KEY_1_PATH),
            jwt.InvalidAudienceError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Invalid Issuer
        (
            generate_rs256_jwt(key_file=TEST_KEY_1_PATH, issuer="invalid-issuer"),
            expiring_value_for_key(TEST_KEY_1_PATH),
            jwt.InvalidIssuerError,
            generate_kid(load_rsa_pk(TEST_KEY_1_PATH)),
        ),
        # Invalid Signature
        (
            generate_rs256_jwt(key_file=TEST_KEY_1_PATH, kid_override=generate_kid(load_rsa_pk(TEST_KEY_2_PATH))),
            expiring_value_for_key(TEST_KEY_2_PATH),
            jwt.InvalidSignatureError,
            generate_kid(load_rsa_pk(TEST_KEY_2_PATH)),
        ),
    ],
)
@pytest.mark.anyio
async def test_validate_azure_ad_token(
    token: str,
    cache_result: Optional[ExpiringValue[JWK]],
    expected_error: Optional[type],
    expected_kid: str,
):
    """Runs through all the ways we validate tokens to ensure the behaviour is valid for all the ways a token
    can be wrong"""

    # Arrange
    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    mock_cache = mock.Mock()
    mock_cache.get_value = mock.Mock(return_value=cache_result)

    # Act
    if expected_error:
        with pytest.raises(expected_error):
            await validate_azure_ad_token(cfg, mock_cache, token)
    else:
        await validate_azure_ad_token(cfg, mock_cache, token)

    # Assert
    mock_cache.get_value.assert_called_once_with(cfg, expected_kid)
