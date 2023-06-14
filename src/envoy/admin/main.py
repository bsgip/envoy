import logging

import uvicorn
from fastapi import Depends, FastAPI
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware

from envoy.admin.api import routers
from envoy.admin.api.depends import AdminAuthDepends
from envoy.admin.settings import AppSettings, settings


def generate_app(new_settings: AppSettings):
    """Generates a new app instance utilising the specific settings instance"""
    admin_auth = AdminAuthDepends(settings.admin_username, settings.admin_password)
    new_app = FastAPI(**new_settings.fastapi_kwargs, dependencies=[Depends(admin_auth)])
    new_app.add_middleware(SQLAlchemyMiddleware, **new_settings.db_middleware_kwargs)
    for router in routers:
        new_app.include_router(router)
    return new_app


# Setup logs
logging.basicConfig(style="{", level=logging.INFO)

# Setup app
app = generate_app(settings)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9999)
