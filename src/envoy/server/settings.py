from typing import Any, Dict

from pydantic import BaseSettings, PostgresDsn


class AppSettings(BaseSettings):
    debug: bool = False
    docs_url: str = "/docs"
    openapi_prefix: str = ""
    openapi_url: str = "/openapi.json"
    redoc_url: str = "/redoc"
    title: str = "envoy"
    version: str = "0.0.0"

    cert_pem_header: str = "x-forwarded-client-cert"
    default_timezone: str = "Australia/Brisbane"

    database_url: PostgresDsn
    commit_on_exit: str = False

    class Config:
        validate_assignment = True
        env_file: str = '.env'
        env_file_encoding: str = 'utf-8'

    @property
    def fastapi_kwargs(self) -> Dict[str, Any]:
        return {
            "debug": self.debug,
            "docs_url": self.docs_url,
            "openapi_prefix": self.openapi_prefix,
            "openapi_url": self.openapi_url,
            "redoc_url": self.redoc_url,
            "title": self.title,
            "version": self.version,
        }

    @property
    def db_middleware_kwargs(self) -> Dict[str, Any]:
        return {"db_url": self.database_url, "commit_on_exit": self.commit_on_exit}


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""
    return AppSettings()


settings = generate_settings()
