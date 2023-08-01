from http import HTTPStatus

import jwt
from fastapi import HTTPException, Request

from envoy.server.api.auth.azure import (
    AzureADManagedIdentityConfig,
    UnableToContactAzureServicesError,
    update_jwk_cache,
    validate_azure_ad_token,
)
from envoy.server.api.auth.jwks import JWK
from envoy.server.cache import AsyncCache
from envoy.server.exception import UnauthorizedError


class AzureADAuthDepends:
    """Dependency class for handling authentication from an Azure Active Directory deployment that will be receiving
    a JWT bearer token signed by an IDP for the specified tenant. It will be using the VM managed identity
    for all parties (services forwarding the requests and the host for this server instance)
    """

    ad_config: AzureADManagedIdentityConfig
    cache: AsyncCache[str, JWK]

    def __init__(self, tenant_id: str, client_id: str, valid_issuer: str):
        # fastapi will always return headers in lowercase form
        self.ad_config = AzureADManagedIdentityConfig(
            tenant_id=tenant_id, client_id=client_id, valid_issuer=valid_issuer
        )
        self.cache = AsyncCache(update_fn=update_jwk_cache)

    async def __call__(self, request: Request):
        # Extract bearer token
        cert_header_val = request.headers.get("authorization", None)
        if not cert_header_val:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Missing Authorization header.",
            )

        token_parts = cert_header_val.split(" ")
        if len(token_parts) != 2 or (token_parts[0].lower() != "bearer"):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Missing Authorization header with bearer token.",
            )

        token = token_parts[1]

        try:
            await validate_azure_ad_token(self.ad_config, self.cache, token)
        except UnableToContactAzureServicesError:
            raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unable to access auth services.")
        except UnauthorizedError:
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Malformed Azure AD Token")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid Azure AD Token")
        except Exception:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Unknown error")
