from typing import Any, Dict, Optional

from pydantic import BaseSettings, PostgresDsn


class AppSettings(BaseSettings):
    debug: bool = False
    docs_url: str = "/docs"
    openapi_prefix: str = ""
    openapi_url: str = "/openapi.json"
    redoc_url: str = "/redoc"
    title: str = "envoy"
    version: str = "0.0.0"

    cert_header: str = "x-forwarded-client-cert"  # either client certificate in PEM format or the sha256 fingerprint
    default_timezone: str = "Australia/Brisbane"

    azure_ad_tenant_id: Optional[str] = None  # Tenant ID of the Azure AD deployment (if none - disables Azure AD Auth)
    azure_ad_client_id: Optional[str] = None  # Client ID of the app in the Azure AD (if none - disables Azure AD Auth)
    azure_ad_valid_issuer: Optional[str] = None  # Valid Issuer of tokens in the Azure AD (if none - no Azure AD Auth)
    azure_ad_db_resource_id: Optional[str] = None  # Will be used to mint AD tokens as a database password alternative
    azure_ad_db_refresh_secs: int = (
        14400  # How frequently (in seconds) will the Azure AD DB token be manually refreshed. Default 4 hours.
    )

    database_url: PostgresDsn
    commit_on_exit: bool = False

    class Config:
        validate_assignment = True
        env_file: str = ".env"
        env_file_encoding: str = "utf-8"

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

    @property
    def azure_ad_kwargs(self) -> Optional[dict[str, Any]]:
        """Returns the Azure Active Directory configuration (if fully specified) or none otherwise"""
        client_id = self.azure_ad_client_id
        tenant_id = self.azure_ad_tenant_id
        issuer = self.azure_ad_valid_issuer
        if client_id and tenant_id and issuer:
            return {"client_id": client_id, "tenant_id": tenant_id, "issuer": issuer}
        else:
            return None


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    # Silenced complaints about database_url - keeping mypy happy here is tricky (for certain python versions).
    # The "cost" of not having it set will be caught by our test coverage - this is an error we can ignore
    return AppSettings()  # type: ignore  [call-arg]


settings = generate_settings()
