import base64
from dataclasses import dataclass
from typing import Union

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers


@dataclass
class JWK:
    key_id: str  # The unique ID identifying this JWK
    use: str  # Public key use - eg "sig" for signing
    key_type: str  # Key type - eg "RSA"
    rsa_exponent: int  # Decoded RSA exponent (referred to as e)
    rsa_modulus: int  # Decoded RSA modulus (referred to as n)
    pem_public: str  # RSA PEM public key for this JWK


def ensure_bytes(key: Union[str, bytes]) -> bytes:
    """Ensures a value is bytes - converting a string to UTF-8 bytes if required"""
    if isinstance(key, str):
        key = key.encode("utf-8")
    return key


def decode_b64_bytes_to_int(val: str) -> int:
    """Decodes a base64 encoded value into a raw integer"""
    decoded = base64.urlsafe_b64decode(ensure_bytes(val) + b"==")
    return int.from_bytes(decoded, "big")


def rsa_pem_from_jwk(n: int, e: int) -> bytes:
    """Generates an RSA public key for a given"""
    return (
        RSAPublicNumbers(n=n, e=e)
        .public_key(default_backend())
        .public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
    )
