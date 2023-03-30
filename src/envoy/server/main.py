import logging

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware

from envoy.server.api import routers
from envoy.server.api.depends import LFDIAuthDepends
from envoy.server.api.error_handler import general_exception_handler, http_exception_handler
from envoy.server.settings import AppSettings


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""
    return AppSettings()


def generate_app(new_settings: AppSettings):
    """Generates a new app instance utilising the specific settings instance"""
    lfdi_auth = LFDIAuthDepends(new_settings.cert_pem_header)
    new_app = FastAPI(**new_settings.fastapi_kwargs, dependencies=[Depends(lfdi_auth)])
    new_app.add_middleware(SQLAlchemyMiddleware, **new_settings.db_middleware_kwargs)
    for router in routers:
        new_app.include_router(router)
    new_app.add_exception_handler(HTTPException, http_exception_handler)
    new_app.add_exception_handler(Exception, general_exception_handler)
    return new_app


# Setup logs
logging.basicConfig(style="{", level=logging.INFO)

# Setup app
settings = generate_settings()
app = generate_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
