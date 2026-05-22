from typing import Any

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


def generate_middleware_kwargs(
    database_url: str,
    commit_on_exit: bool,
    sqlalchemy_engine_args: dict[str, Any] | None,
    azure_ad_db_resource_id: str | None,
    azure_ad_db_refresh_secs: int | None,
) -> dict[str, Any]:
    """Generates kwargs for SQLAlchemyMiddleware for a given set of settings values"""
    settings: dict[str, str | bool | dict] = {"db_url": database_url, "commit_on_exit": commit_on_exit}

    engine_args = sqlalchemy_engine_args.copy() if sqlalchemy_engine_args is not None else {}

    # this setting causes the pool to recycle connections after the given number of seconds has passed
    # It will ensure that connections won't stay live in the pool after the tokens are refreshed
    if azure_ad_db_resource_id and azure_ad_db_refresh_secs:
        engine_args["pool_recycle"] = azure_ad_db_refresh_secs

    if engine_args:
        settings["engine_args"] = engine_args
    return settings


class CommonSettings(BaseSettings):
    """Settings that are common across all envoy services"""

    model_config = {"validate_assignment": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    enable_notifications: bool | None = None  # Will pub/sub generate outgoing Notifications to active subs?
    rabbit_mq_broker_url: str | None = None  # RabbitMQ URL pointing to a running server (for pub/sub)

    azure_ad_tenant_id: str | None = None  # Tenant ID of the Azure AD deployment (if none - disables Azure AD Auth)
    azure_ad_client_id: str | None = None  # Client ID of the app in the Azure AD (if none - disables Azure AD Auth)
    azure_ad_valid_issuer: str | None = None  # Valid Issuer of tokens in the Azure AD (if none - no Azure AD Auth)
    azure_ad_db_resource_id: str | None = None  # Will be used to mint AD tokens as a database password alternative
    azure_ad_db_refresh_secs: int = (
        14400  # How frequently (in seconds) will the Azure AD DB token be manually refreshed. Default 4 hours.
    )

    database_url: PostgresDsn
    default_timezone: str = "Australia/Brisbane"

    href_prefix: str | None = None  # Will ensure all outgoing href's are prefixed with this value (None = disabled)
    iana_pen: int = 0  # The IANA Private Enterprise Number of the organisation hosting this instance. Encoded in mrids

    sqlalchemy_engine_arguments: dict[str, str | int | float] | None = None

    @property
    def db_middleware_kwargs(self) -> dict[str, Any]:
        return generate_middleware_kwargs(
            database_url=str(self.database_url),
            commit_on_exit=False,
            sqlalchemy_engine_args=self.sqlalchemy_engine_arguments,
            azure_ad_db_resource_id=self.azure_ad_db_resource_id,
            azure_ad_db_refresh_secs=self.azure_ad_db_refresh_secs,
        )

    @property
    def azure_ad_kwargs(self) -> dict[str, Any] | None:
        """Returns the Azure Active Directory configuration (if fully specified) or none otherwise"""
        client_id = self.azure_ad_client_id
        tenant_id = self.azure_ad_tenant_id
        issuer = self.azure_ad_valid_issuer
        if client_id and tenant_id and issuer:
            return {"client_id": client_id, "tenant_id": tenant_id, "issuer": issuer}
        else:
            return None
