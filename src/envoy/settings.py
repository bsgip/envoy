from typing import Any, Dict, Optional

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


def generate_middleware_kwargs(
    database_url: str,
    commit_on_exit: bool,
    azure_ad_db_resource_id: Optional[str],
    azure_ad_db_refresh_secs: Optional[int],
) -> dict[str, Any]:
    """Generates kwargs for SQLAlchemyMiddleware for a given set of settings values"""
    settings = {"db_url": database_url, "commit_on_exit": commit_on_exit}

    # this setting causes the pool to recycle connections after the given number of seconds has passed
    # It will ensure that connections won't stay live in the pool after the tokens are refreshed
    if azure_ad_db_resource_id and azure_ad_db_refresh_secs:
        settings["engine_args"] = {"pool_recycle": azure_ad_db_refresh_secs}
    return settings


class CommonSettings(BaseSettings):
    """Settings that are common across all envoy services"""

    model_config = {"validate_assignment": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    enable_notifications: Optional[bool] = None  # Will pub/sub generate outgoing Notifications to active subs?
    rabbit_mq_broker_url: Optional[str] = None  # RabbitMQ URL pointing to a running server (for pub/sub)

    azure_ad_tenant_id: Optional[str] = None  # Tenant ID of the Azure AD deployment (if none - disables Azure AD Auth)
    azure_ad_client_id: Optional[str] = None  # Client ID of the app in the Azure AD (if none - disables Azure AD Auth)
    azure_ad_valid_issuer: Optional[str] = None  # Valid Issuer of tokens in the Azure AD (if none - no Azure AD Auth)
    azure_ad_db_resource_id: Optional[str] = None  # Will be used to mint AD tokens as a database password alternative
    azure_ad_db_refresh_secs: int = (
        14400  # How frequently (in seconds) will the Azure AD DB token be manually refreshed. Default 4 hours.
    )

    database_url: PostgresDsn

    href_prefix: Optional[str] = None  # Will ensure all outgoing href's are prefixed with this value (None = disabled)

    @property
    def db_middleware_kwargs(self) -> Dict[str, Any]:
        return generate_middleware_kwargs(
            database_url=str(self.database_url),
            commit_on_exit=False,
            azure_ad_db_resource_id=self.azure_ad_db_resource_id,
            azure_ad_db_refresh_secs=self.azure_ad_db_refresh_secs,
        )

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
