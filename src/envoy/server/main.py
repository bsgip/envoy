import logging

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware

from envoy.server.api import routers
from envoy.server.api.depends.azure_ad_auth import AzureADAuthDepends
from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends
from envoy.server.api.depends.path_prefix import PathPrefixDepends
from envoy.server.api.error_handler import general_exception_handler, http_exception_handler
from envoy.server.database import enable_dynamic_azure_ad_database_credentials
from envoy.server.settings import AppSettings, settings

# Setup logs
logging.basicConfig(style="{", level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_app(new_settings: AppSettings):
    """Generates a new app instance utilising the specific settings instance"""

    lfdi_auth = LFDIAuthDepends(new_settings.cert_header)
    global_dependencies = [Depends(lfdi_auth)]
    lifespan_manager = None

    # if href_prefix is specified - include the PathPrefixDepends
    if new_settings.href_prefix:
        global_dependencies.append(Depends(PathPrefixDepends(new_settings.href_prefix)))

    # Azure AD Auth is an optional extension enabled via configuration settings
    azure_ad_settings = new_settings.azure_ad_kwargs
    if azure_ad_settings:
        logger.info(f"Enabling AzureADAuth: {azure_ad_settings}")
        azure_ad_auth = AzureADAuthDepends(
            tenant_id=azure_ad_settings["tenant_id"],
            client_id=azure_ad_settings["client_id"],
            valid_issuer=azure_ad_settings["issuer"],
        )
        global_dependencies.insert(0, Depends(azure_ad_auth))

        # Optionally enable the dynamic database credentials
        resource_id = new_settings.azure_ad_db_resource_id
        update_frequency_seconds = new_settings.azure_ad_db_refresh_secs
        if resource_id and update_frequency_seconds:
            logger.info(
                f"Enabling AzureAD Dynamic DB Credentials: rsc_id: '{resource_id}' freq_sec: {update_frequency_seconds}"
            )
            lifespan_manager = enable_dynamic_azure_ad_database_credentials(
                tenant_id=azure_ad_settings["tenant_id"],
                client_id=azure_ad_settings["client_id"],
                resource_id=resource_id,
                manual_update_frequency_seconds=update_frequency_seconds,
            )

    new_app = FastAPI(**new_settings.fastapi_kwargs, dependencies=global_dependencies, lifespan=lifespan_manager)
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
