import uvicorn
from fastapi import Depends, FastAPI
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware

from server.api.depends import LFDIAuthDepends
from server.api.sep2.time import router as tm_router
from server.settings import AppSettings


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""
    return AppSettings()


def generate_app(new_settings: AppSettings):
    """Generates a new app instance utilising the specific settings instance"""
    lfdi_auth = LFDIAuthDepends(new_settings.cert_pem_header)
    new_app = FastAPI(**new_settings.fastapi_kwargs, dependencies=[Depends(lfdi_auth)])
    new_app.add_middleware(SQLAlchemyMiddleware, **new_settings.db_middleware_kwargs)
    new_app.include_router(tm_router, tags=["time"])
    return new_app


settings = generate_settings()
app = generate_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
