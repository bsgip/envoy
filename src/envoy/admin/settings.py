from typing import Any, Dict, Optional

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

from envoy.server.settings import generate_middleware_kwargs


class AppSettings(BaseSettings):
    model_config = {"validate_assignment": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    debug: bool = False
    docs_url: str = "/docs"
    openapi_prefix: str = ""
    openapi_url: str = "/openapi.json"
    redoc_url: str = "/redoc"
    title: str = "envoy-admin"
    version: str = "0.0.0"

    default_timezone: str = "Australia/Brisbane"

    database_url: PostgresDsn
    commit_on_exit: bool = False

    admin_username: str
    admin_password: str

    azure_ad_tenant_id: Optional[str] = None  # Tenant ID of the Azure AD deployment (if none - disables Azure AD Auth)
    azure_ad_client_id: Optional[str] = None  # Client ID of the app in the Azure AD (if none - disables Azure AD Auth)
    azure_ad_db_resource_id: Optional[str] = None  # Will be used to mint AD tokens as a database password alternative
    azure_ad_db_refresh_secs: int = (
        14400  # How frequently (in seconds) will the Azure AD DB token be manually refreshed. Default 4 hours.
    )

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
        return generate_middleware_kwargs(
            database_url=str(self.database_url),
            commit_on_exit=self.commit_on_exit,
            azure_ad_db_resource_id=self.azure_ad_db_resource_id,
            azure_ad_db_refresh_secs=self.azure_ad_db_refresh_secs,
        )


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    # Silenced complaints about database_url - keeping mypy happy here is tricky (for certain python versions).
    # The "cost" of not having it set will be caught by our test coverage - this is an error we can ignore
    return AppSettings()  # type: ignore  [call-arg]


settings = generate_settings()
