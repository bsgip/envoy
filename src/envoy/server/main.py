import logging

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware
from lxml.etree import XMLSyntaxError  # type: ignore # nosec: This will need to be addressed with pydantic-xml
from pydantic_core import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from envoy.notification.handler import enable_notification_client
from envoy.server.api.depends.allow_nmi_updates import ALLOW_NMI_UPDATES_ATTR
from envoy.server.api.depends.azure_ad_auth import AzureADAuthDepends
from envoy.server.api.depends.default_doe import DefaultDoeDepends
from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends
from envoy.server.api.depends.nmi_validator import NMI_VALIDATOR_ATTR
from envoy.server.api.depends.request_state_settings import RequestStateSettingsDepends
from envoy.server.api.error_handler import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    xml_exception_handler,
)
from envoy.server.api.router import routers, unsecured_routers
from envoy.server.database import enable_dynamic_azure_ad_database_credentials
from envoy.server.lifespan import generate_combined_lifespan_manager
from envoy.server.endpoint_exclusion import generate_routers_with_excluded_endpoints
from envoy.server.settings import AppSettings, settings

# Setup logs
logging.basicConfig(style="{", level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_app(new_settings: AppSettings) -> FastAPI:
    """Generates a new app instance utilising the specific settings instance"""

    lfdi_auth = LFDIAuthDepends(
        cert_header=new_settings.cert_header, allow_device_registration=new_settings.allow_device_registration
    )
    global_dependencies = [Depends(lfdi_auth)]
    lifespan_managers = []

    global_dependencies.append(Depends(RequestStateSettingsDepends(new_settings.href_prefix, new_settings.iana_pen)))

    # if default DOE is specified - include the DefaultDoeDepends
    if new_settings.use_global_default_doe_fallback:
        global_dependencies.append(Depends(DefaultDoeDepends(**new_settings.default_doe_configuration)))

    # Setup notification broker connection for sep2 pub/sub support
    if new_settings.enable_notifications:
        lifespan_managers.append(enable_notification_client(new_settings.rabbit_mq_broker_url))

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
            lifespan_managers.append(
                enable_dynamic_azure_ad_database_credentials(
                    tenant_id=azure_ad_settings["tenant_id"],
                    client_id=azure_ad_settings["client_id"],
                    resource_id=resource_id,
                    manual_update_frequency_seconds=update_frequency_seconds,
                )
            )

    new_app = FastAPI(**new_settings.fastapi_kwargs, lifespan=generate_combined_lifespan_manager(lifespan_managers))
    new_app.add_middleware(SQLAlchemyMiddleware, **new_settings.db_middleware_kwargs)

    # install routers
    if new_settings.exclude_endpoints:
        routers_to_include = generate_routers_with_excluded_endpoints(routers, new_settings.exclude_endpoints)
    else:
        routers_to_include = routers

    for router in routers_to_include:
        new_app.include_router(router, dependencies=global_dependencies)
    for router in unsecured_routers:
        new_app.include_router(router)

    # Manually inject configured NMI validator into app state
    if new_settings.nmi_validation and new_settings.nmi_validation.nmi_validation_enabled:
        setattr(new_app.state, NMI_VALIDATOR_ATTR, new_settings.nmi_validation.validator)
    else:
        setattr(new_app.state, NMI_VALIDATOR_ATTR, None)

    # Inject allow nmi updates setting
    setattr(new_app.state, ALLOW_NMI_UPDATES_ATTR, new_settings.allow_nmi_updates)

    new_app.add_exception_handler(HTTPException, http_exception_handler)
    new_app.add_exception_handler(ValidationError, validation_exception_handler)
    new_app.add_exception_handler(XMLSyntaxError, xml_exception_handler)
    new_app.add_exception_handler(Exception, general_exception_handler)
    new_app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    return new_app


# Setup app
app = generate_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
