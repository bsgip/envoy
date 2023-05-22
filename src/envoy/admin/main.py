import logging

import uvicorn
from fastapi import Depends, FastAPI, HTTPException

from envoy.admin.api.router import router

# from fastapi_async_sqlalchemy import SQLAlchemyMiddleware


# TODO swap these to envoy.admin equivalents
# from envoy.server.api import routers
# from envoy.server.api.depends import LFDIAuthDepends  # TODO unclear?
# from envoy.server.api.error_handler import general_exception_handler, http_exception_handler  # TODO shared?
# from envoy.server.settings import AppSettings, settings  # TODO

# def generate_app(new_settings: AppSettings):
#     """Generates a new app instance utilising the specific settings instance"""
#     lfdi_auth = LFDIAuthDepends(new_settings.cert_pem_header)
#     new_app = FastAPI(**new_settings.fastapi_kwargs, dependencies=[Depends(lfdi_auth)])
#     new_app.add_middleware(SQLAlchemyMiddleware, **new_settings.db_middleware_kwargs)
#     for router in routers:
#         new_app.include_router(router)
#     new_app.add_exception_handler(HTTPException, http_exception_handler)
#     new_app.add_exception_handler(Exception, general_exception_handler)
#     return new_app


# Setup logs
logging.basicConfig(style="{", level=logging.INFO)

# Setup app
# app = generate_app(settings)

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9999)
