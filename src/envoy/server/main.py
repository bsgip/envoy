import logging

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware

from envoy.server.api import routers
from envoy.server.api.depends.azure_ad_auth import AzureADAuthDepends
from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends
from envoy.server.api.error_handler import general_exception_handler, http_exception_handler
from envoy.server.settings import AppSettings, settings

# Setup logs
logging.basicConfig(style="{", level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_app(new_settings: AppSettings):
    """Generates a new app instance utilising the specific settings instance"""
    lfdi_auth = LFDIAuthDepends(new_settings.cert_header)
    global_dependencies = [Depends(lfdi_auth)]

    # Azure AD Auth is an optional extension enabled via configuration settings
    client_id = new_settings.azure_ad_client_id
    tenant_id = new_settings.azure_ad_tenant_id
    issuer = new_settings.azure_ad_valid_issuer
    if client_id and tenant_id and issuer:
        logger.info(f"Enabling AzureADAuth: Client: {client_id} Tenant: {tenant_id} Issuer: {issuer}")
        azure_ad_auth = AzureADAuthDepends(
            tenant_id=tenant_id,
            client_id=client_id,
            valid_issuer=issuer,
        )
        global_dependencies.insert(0, Depends(azure_ad_auth))

    new_app = FastAPI(**new_settings.fastapi_kwargs, dependencies=global_dependencies)
    new_app.add_middleware(SQLAlchemyMiddleware, **new_settings.db_middleware_kwargs)
    for router in routers:
        new_app.include_router(router)
    new_app.add_exception_handler(HTTPException, http_exception_handler)
    new_app.add_exception_handler(Exception, general_exception_handler)
    return new_app


# Setup app
app = generate_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
