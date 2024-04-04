import logging

import uvicorn
from fastapi import Depends, FastAPI
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware

from envoy.admin.api import routers
from envoy.admin.api.depends import AdminAuthDepends
from envoy.admin.settings import AppSettings, settings
from envoy.notification.handler import enable_notification_client
from envoy.server.database import enable_dynamic_azure_ad_database_credentials
from envoy.server.lifespan import generate_combined_lifespan_manager

# Setup logs
logging.basicConfig(style="{", level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_app(new_settings: AppSettings) -> FastAPI:
    """Generates a new app instance utilising the specific settings instance"""
    # Optionally enable the dynamic database credentials
    resource_id = new_settings.azure_ad_db_resource_id
    update_frequency_seconds = new_settings.azure_ad_db_refresh_secs
    tenant_id = new_settings.azure_ad_tenant_id
    client_id = new_settings.azure_ad_client_id

    lifespan_managers = []

    if new_settings.enable_notifications:
        lifespan_managers.append(enable_notification_client(new_settings.rabbit_mq_broker_url))

    if tenant_id and client_id and resource_id and update_frequency_seconds:
        logger.info(
            f"Enabling AzureAD Dynamic DB Credentials: rsc_id: '{resource_id}' freq_sec: {update_frequency_seconds}"
        )
        lifespan_managers.append(
            enable_dynamic_azure_ad_database_credentials(
                tenant_id=tenant_id,
                client_id=client_id,
                resource_id=resource_id,
                manual_update_frequency_seconds=update_frequency_seconds,
            )
        )

    admin_auth = AdminAuthDepends(settings.admin_username, settings.admin_password)
    new_app = FastAPI(
        **new_settings.fastapi_kwargs,
        dependencies=[Depends(admin_auth)],
        lifespan=generate_combined_lifespan_manager(lifespan_managers),
    )
    new_app.add_middleware(SQLAlchemyMiddleware, **new_settings.db_middleware_kwargs)
    for router in routers:
        new_app.include_router(router)

    return new_app


# Setup app
app = generate_app(settings)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9999)
