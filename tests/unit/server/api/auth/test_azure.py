import json
import unittest.mock as mock
from http import HTTPStatus

import pytest
from httpx import Response

from envoy.server.api.auth.azure import AzureADManagedIdentityConfig, parse_from_jwks_json, validate_azure_ad_token
from envoy.server.api.auth.jwks import JWK
from tests.unit.jwt import (
    DEFAULT_CLIENT_ID,
    DEFAULT_ISSUER,
    DEFAULT_TENANT_ID,
    TEST_KEY_1_PATH,
    TEST_KEY_2_PATH,
    generate_jwk_defn,
    generate_rs256_jwt,
    load_pk,
)


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
    assert len(set([v.pem_public_bytes for v in result_dict.values()])) == len(
        result_dict
    ), "All PEM bytes should be distinct"

    jwk = result_dict["DqUu8gf-nAgcyjP3-SuplNAXAnc"]
    assert jwk.key_type == "RSA"
    assert jwk.key_id == "DqUu8gf-nAgcyjP3-SuplNAXAnc"
    assert isinstance(jwk.rsa_exponent, int)
    assert jwk.rsa_exponent != 0
    assert isinstance(jwk.rsa_modulus, int)
    assert jwk.rsa_modulus != 0
    assert len(jwk.pem_public_bytes) != 0


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
    assert len(jwk.pem_public_bytes) != 0


def generate_test_jwks_response(keys: list) -> str:
    return json.dumps({"keys": [generate_jwk_defn(key) for key in keys]})


@pytest.mark.anyio
@mock.patch("envoy.server.api.auth.azure.AsyncClient")
async def test_validate_azure_ad_token_full_token(mock_AsyncClient: mock.MagicMock):
    """Tests that a correctly signed Azure AD token validates"""

    # Mocking out the async client
    mock_client = mock.Mock()
    mock_client.get = mock.Mock()
    mock_AsyncClient.side_effect = mock_client

    cfg = AzureADManagedIdentityConfig(DEFAULT_TENANT_ID, DEFAULT_CLIENT_ID, DEFAULT_ISSUER)
    token = generate_rs256_jwt(key_file=TEST_KEY_1_PATH)
    pk1 = load_pk(TEST_KEY_1_PATH)
    pk2 = load_pk(TEST_KEY_2_PATH)

    raw_json_response = generate_test_jwks_response([pk2, pk1])
    mock_client.get.return_value = Response(status_code=HTTPStatus.OK, content=raw_json_response)

    await validate_azure_ad_token(cfg, token)

    mock_client.get.assert_called_once()
