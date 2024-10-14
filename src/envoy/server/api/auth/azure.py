import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Iterable
from urllib.parse import quote

import jwt
from httpx import AsyncClient

from envoy.server.api.auth.jwks import JWK, decode_b64_bytes_to_int, rsa_pem_from_jwk
from envoy.server.cache import AsyncCache, ExpiringValue
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


@dataclass
class AzureADResourceTokenConfig:
    """Configuration setup for an Azure Active Directory auth scenario where managed identity is used to identify
    all VMs in the deployment. This config will be utilised for generating tokens for a specific resource"""

    tenant_id: str  # The tenant ID that will be used to generate Azure AD tokens
    client_id: str  # The client id of the VM managed identity that will be generating/validating Azure AD tokens
    resource_id: str  # The resource ID that tokens will be requested for


@dataclass
class AzureADToken:
    token: str  # The actual bearer token to be included in requests to the specified resource
    resource_id: str  # The resource_id that the token is for
    expiry: datetime  # The exact datetime when the token expires


_TOKEN_URI_FORMAT = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource={resource}&client_id={client_id}"  # noqa e501 # nosec
_PUBLIC_KEY_URI_FORMAT = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
TOKEN_EXPIRY_BUFFER_SECONDS = 120  # Tokens will have their expiry reduced by this many seconds (to act as a buffer)
REQUEST_TIMEOUT_SECONDS = 60


def parse_from_jwks_json(keys: Iterable[dict[str, str]]) -> dict[str, ExpiringValue[JWK]]:
    """Given a list of keys in the below form - parse out a dict of JWK instances
    {
        "kty": "RSA",
        "use": "sig",
        "kid": "abc123",
        "n": "b64 encoded value",
        "e": "b64 encoded value",
    }"""

    jwks: dict[str, ExpiringValue[JWK]] = {}
    for key in keys:
        key_type = key["kty"]
        use = key["use"]
        key_id = key["kid"]

        if (not key_id) or (key_type != "RSA") or (use != "sig"):
            continue

        n = decode_b64_bytes_to_int(key["n"])
        e = decode_b64_bytes_to_int(key["e"])

        jwks[key_id] = ExpiringValue(
            expiry=None,
            value=JWK(
                key_id=key_id,
                use=use,
                key_type=key_type,
                rsa_exponent=e,
                rsa_modulus=n,
                pem_public=rsa_pem_from_jwk(n, e).decode("utf-8"),
            ),
        )

    return jwks


async def update_jwk_cache(cfg: AzureADManagedIdentityConfig) -> dict[str, ExpiringValue[JWK]]:
    """Performs an update for a JWK cache that's compatible with an AsyncCache update_fn

    This will return the latest values from the Azure AD IDP for the current tenant

    raises UnableToContactAzureServicesError on error"""

    uri = _PUBLIC_KEY_URI_FORMAT.format(tenant_id=quote(cfg.tenant_id))
    logger.info(f"Updating jwk cache via uri {uri}")
    async with AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        try:
            response = await client.get(uri)
        except Exception as ex:
            logger.error(f"Exception {ex} trying to access Azure keys from {uri}")
            raise UnableToContactAzureServicesError("Exception trying to access Azure keys")

        if response.status_code != HTTPStatus.OK:
            logger.error(f"Received HTTP {response.status_code} trying to access Azure keys from {uri}")
            raise UnableToContactAzureServicesError(f"Received HTTP {response.status_code} trying to access Azure keys")

        body = response.json()
        updated_cache = parse_from_jwks_json(body["keys"])
        logger.debug(f"Updated jwk cache with {len(updated_cache)} items")
        return updated_cache


async def validate_azure_ad_token(cfg: AzureADManagedIdentityConfig, cache: AsyncCache[str, JWK], token: str) -> None:
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
    jwk = await cache.get_value(cfg, key_id)
    if not jwk:
        raise UnauthorizedError(f"jwk key_id '{key_id}' not found")

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


async def request_azure_ad_token(cfg: AzureADResourceTokenConfig) -> AzureADToken:
    """Requests an Azure AD token for the specified resource_id on behalf of the
    specified AzureADManagedIdentityConfig

    raises UnableToContactAzureServicesError on error"""

    uri = _TOKEN_URI_FORMAT.format(resource=quote(cfg.resource_id), client_id=quote(cfg.client_id))
    async with AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        try:
            response = await client.get(uri, headers={"Metadata": "true"})
        except Exception as ex:
            logger.error(f"Exception {ex} trying to access token from {uri}")
            raise UnableToContactAzureServicesError("Exception trying to access Azure token service")

        if response.status_code != HTTPStatus.OK:
            logger.error(f"Received HTTP {response.status_code} trying to access Azure token from {uri}")
            raise UnableToContactAzureServicesError(f"Received HTTP {response.status_code} fetching Azure AD token")

        body = response.json()
        access_token = body["access_token"]
        expiry = datetime.fromtimestamp(int(body["expires_on"]), tz=timezone.utc)
        return AzureADToken(token=access_token, resource_id=cfg.resource_id, expiry=expiry)


async def update_azure_ad_token_cache(cfg: AzureADResourceTokenConfig) -> dict[str, ExpiringValue[str]]:
    """maps request_azure_ad_token into a form that is compatible with an AsyncCache update function

    Returns a dictionary with a single entry keyed by the resource ID, containing the access token value"""
    azure_ad_token = await request_azure_ad_token(cfg)
    expiry = azure_ad_token.expiry + timedelta(seconds=-TOKEN_EXPIRY_BUFFER_SECONDS)  # Expire the tokens early
    return {cfg.resource_id: ExpiringValue(expiry=expiry, value=azure_ad_token.token)}
