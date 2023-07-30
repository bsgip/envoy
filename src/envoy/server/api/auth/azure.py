import logging
from asyncio import Lock
from dataclasses import dataclass
from http import HTTPStatus
from typing import Iterable, Optional

import jwt
from httpx import AsyncClient

from envoy.server.api.auth.jwks import JWK, decode_b64_bytes_to_int, rsa_pem_from_jwk
from envoy.server.exception import InternalError, UnauthorizedError

logger = logging.getLogger(__name__)


class UnableToContactAzureServicesError(InternalError):
    """Raised when Azure internal services aren't able to be accessed for whatever reason"""

    pass


@dataclass
class AzureADManagedIdentityConfig:
    """Configuration setup for an Azure Active Directory auth scenario where managed identity is used to identify
    all VMs in the deployment. Connections between VM's will be authorised by the Azure AD JWK tokens"""

    tenant_id: str  # The tenant ID that will be used to generate Azure AD tokens
    client_id: str  # The client id of the VM managed identity that will be generating/validating Azure AD tokens
    valid_issuer: str  # The issuer of the incoming tokens


_PUBLIC_KEY_URI_FORMAT = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
_JWKS_CACHE: dict[str, JWK] = {}  # JWK instances keyed by their key_id
_JWKS_CACHE_UPDATE_LOCK = Lock()


def _get_jwk_from_cache(key_id: str) -> Optional[JWK]:
    """Attempts to fetch the specific JWK by key_id from the internal cache. Returns None if it DNE in the cache
    No attempts to update cache will be made"""
    return _JWKS_CACHE.get(key_id, None)


async def clear_jwks_cache():
    """Resets the internal jwks cache to empty - will be async safe but not thread safe"""
    global _JWKS_CACHE

    async with _JWKS_CACHE_UPDATE_LOCK:
        _JWKS_CACHE = {}


def parse_from_jwks_json(keys: Iterable[dict[str, str]]) -> dict[str, JWK]:
    """Given a list of keys in the below form - parse out a dict of JWK instances
    {
        "kty": "RSA",
        "use": "sig",
        "kid": "abc123",
        "n": "b64 encoded value",
        "e": "b64 encoded value",
    }"""

    jwks: dict[str, JWK] = {}
    for key in keys:
        key_type = key["kty"]
        use = key["use"]
        key_id = key["kid"]

        if (not key_id) or (key_type != "RSA") or (use != "sig"):
            continue

        n = decode_b64_bytes_to_int(key["n"])
        e = decode_b64_bytes_to_int(key["e"])

        jwks[key_id] = JWK(
            key_id=key_id,
            use=use,
            key_type=key_type,
            rsa_exponent=e,
            rsa_modulus=n,
            pem_public=rsa_pem_from_jwk(n, e).decode("utf-8"),
        )

    return jwks


async def _update_jwk_cache(cfg: AzureADManagedIdentityConfig):
    """Internal method - It is assumed that _JWKS_CACHE_UPDATE_LOCK has been acquired

    This will update _JWKS_CACHE with the latest values from the Azure AD IDP for the current tenant

    raises UnableToContactAzureServicesError on error"""
    global _JWKS_CACHE

    uri = _PUBLIC_KEY_URI_FORMAT.format(tenant_id=cfg.tenant_id)
    logger.info(f"Updating jwk cache via uri {uri}")
    async with AsyncClient() as client:
        response = await client.get(uri)
        if response.status_code != HTTPStatus.OK:
            logger.error(f"Received HTTP {response.status_code} trying to access Azure keys from {uri}")
            raise UnableToContactAzureServicesError(f"Received HTTP {response.status_code} trying to access Azure keys")

        body = response.json()
        _JWKS_CACHE = parse_from_jwks_json(body["keys"])
        logger.debug(f"Updated jwk cache with {len(_JWKS_CACHE)} items")


async def get_jwk(cfg: AzureADManagedIdentityConfig, key_id: str) -> JWK:
    """Attempts to fetch the specified JWK by key_id. The internal cache will be utilised first and updated
    if the key_id is not found. Will raise a UnauthorizedError if the JWK cannot be found"""

    # use cache first from outside the lock - the hope is that 99% of requests go this route
    jwk = _get_jwk_from_cache(key_id)
    if jwk:
        return jwk

    # Otherwise acquire the async lock (it won't work with threads - only coroutines)
    # to ensure only one coroutine is doing an update at a time
    async with _JWKS_CACHE_UPDATE_LOCK:
        # Double check that the cache hasn't updated while we were waiting
        jwk = _get_jwk_from_cache(key_id)
        if jwk:
            return jwk

        # Perform the update
        await _update_jwk_cache(cfg)

        # Now it's the final attempt - either get it or raise an error
        # we do this test from within the lock so we're sure that no other updates
        # can occur - basically - if the ID DNE - it's 100% not in the set of valid public keys
        jwk = _get_jwk_from_cache(key_id)
        if jwk:
            return jwk
        else:
            raise UnauthorizedError(f"jwk key_id '{key_id}' not found")


async def validate_azure_ad_token(cfg: AzureADManagedIdentityConfig, token: str):
    """
    Given a raw JSON Web Token from Azure AD - decompose and validate that it's authorised for accessing this
    server instance (defined by cfg). This function will utilise an internal cache to minimise outgoing validation
    requests

    raises UnableToContactAzureServicesError if the underlying Azure AD services cant be accessed
    raises UnauthorizedError if the token is malformed
    raises jwt.*Error on token validation errors"""

    # Start by pulling apart the token (without validating it yet)
    headers = jwt.get_unverified_header(token)
    if not headers:
        raise UnauthorizedError("missing headers from token")

    key_id = headers.get("kid", None)
    if not key_id:
        raise UnauthorizedError("missing kid header from token")

    # Pull the jwk associated with the key_id from our token
    jwk = await get_jwk(cfg, key_id)

    # Decode / Validate the token
    decoded = jwt.decode(
        token,
        jwk.pem_public,
        verify=True,
        algorithms=["RS256"],
        audience=[cfg.client_id],
        issuer=cfg.valid_issuer,
    )

    logger.debug(f"Validated token {decoded}")
