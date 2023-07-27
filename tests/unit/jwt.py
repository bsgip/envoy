import base64
from datetime import datetime, timedelta
from typing import Optional, Union

import jwt
from cryptography.hazmat.primitives import serialization

DEFAULT_TENANT_ID = "my-tenant-id-1"
DEFAULT_CLIENT_ID = "my-client-id-2"
DEFAULT_ISSUER = "https://my.test.issuer:8756/path/"
DEFAULT_SUBJECT_ID = "my-subject-id-123"

TEST_KEY_1_PATH = "tests/data/keys/test_key1"
TEST_KEY_2_PATH = "tests/data/keys/test_key2"


def load_pk(key_path: str):
    with open(key_path) as f:
        return serialization.load_ssh_private_key(f.read().encode(), password=b"")


def generate_jwk_defn(pk: serialization.SSHPrivateKeyTypes) -> dict[str, str]:
    pub = pk.public_key()
    numbers = pub.public_numbers()

    e = base64.b64encode(int(numbers.e).to_bytes(byteorder="big")).decode("utf-8")
    n = base64.b64encode(int(numbers.n).to_bytes(byteorder="big")).decode("utf-8")

    # Doesn't matter how this is generated - just needs to be semi unique
    kid = e[:8] + n[:8]

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
    key_file: str = TEST_KEY_1_PATH,
) -> str:
    """Generates an RS256 signed JWT with the specified set of claims"""
    payload_data: dict[str, Union[int, str]] = {}

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

    pk = load_pk(key_file)
    pk_pem = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    with open(key_file) as f:
        bacon = f.read()

    bacon2 = "\n".join([l.lstrip() for l in bacon.split("\n")])
    return jwt.encode(payload=payload_data, key=bacon2, algorithm="RS256")
