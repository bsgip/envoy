import base64
from datetime import datetime, timedelta
from typing import Optional, Union

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

DEFAULT_TENANT_ID = "my-tenant-id-1"
DEFAULT_CLIENT_ID = "my-client-id-2"
DEFAULT_ISSUER = "https://my.test.issuer:8756/path/"
DEFAULT_SUBJECT_ID = "my-subject-id-123"
DEFAULT_DATABASE_RESOURCE_ID = "my-db-resource-id-456"

TEST_KEY_1_PATH = "tests/data/keys/test_key1.pem"
TEST_KEY_2_PATH = "tests/data/keys/test_key2.pem"


def load_rsa_pk(key_path: str) -> RSAPrivateKey:
    """Given a file path to a PEM encoded private key - load that file into a RSAPrivateKey"""
    with open(key_path) as f:
        pk = serialization.load_pem_private_key(f.read().encode(), password=None)
        if not isinstance(pk, RSAPrivateKey):
            raise Exception(f"Expected RSAPrivateKey but got {type(pk)}")
        return pk


def generate_kid(pk: RSAPrivateKey) -> str:
    """Generates a key id using a simple method that's suitable for tests - dont use this in anything
    resembling a production system"""
    nums = pk.public_key().public_numbers()
    return "custom-" + str(nums.n)[:24] + "|" + str(nums.e)[:24]


def generate_azure_jwk_definition(pk: RSAPrivateKey) -> dict[str, str]:
    """Given a private key - generate a dictionary that models the Azure JWK definition returned from their
    public key endpoint"""
    pub = pk.public_key()
    numbers = pub.public_numbers()

    e = base64.b64encode(int(numbers.e).to_bytes(length=4, byteorder="big")).decode("utf-8")
    n = base64.b64encode(int(numbers.n).to_bytes(length=256, byteorder="big")).decode("utf-8")

    # Doesn't matter how this is generated - just needs to be semi unique
    kid = generate_kid(pk)

    return {
        "kty": "RSA",
        "use": "sig",
        "kid": kid,
        "n": n.replace("=", ""),
        "e": e.replace("=", ""),
    }


def generate_rs256_jwt(
    tenant_id: Optional[str] = DEFAULT_TENANT_ID,
    aud: Optional[str] = DEFAULT_CLIENT_ID,
    sub: Optional[str] = DEFAULT_SUBJECT_ID,
    issuer: Optional[str] = DEFAULT_ISSUER,
    expired: bool = False,
    premature: bool = False,
    kid_override: Optional[str] = None,
    key_file: str = TEST_KEY_1_PATH,
) -> str:
    """Generates an RS256 signed JWT with the specified set of claims"""
    payload_data: dict[str, Union[int, str]] = {}
    payload_header: dict[str, str] = {}

    if tenant_id is not None:
        payload_data["tid"] = tenant_id

    if aud is not None:
        payload_data["aud"] = aud

    if sub is not None:
        payload_data["sub"] = sub

    if issuer is not None:
        payload_data["iss"] = issuer

    if expired:
        payload_data["exp"] = int((datetime.now() + timedelta(minutes=-1)).timestamp())
    else:
        payload_data["exp"] = int((datetime.now() + timedelta(hours=1)).timestamp())

    if premature:
        payload_data["nbf"] = int((datetime.now() + timedelta(hours=1)).timestamp())
    else:
        payload_data["nbf"] = int((datetime.now() + timedelta(minutes=-1)).timestamp())

    pk = load_rsa_pk(key_file)
    pk_pem = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    if kid_override is None:
        payload_header["kid"] = generate_kid(pk)
    else:
        payload_header["kid"] = kid_override

    return jwt.encode(payload=payload_data, headers=payload_header, key=pk_pem, algorithm="RS256")
