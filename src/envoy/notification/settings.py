from typing import Optional

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    model_config = {"validate_assignment": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    title: str = "envoy-notifications"
    version: str = "0.0.0"

    database_url: PostgresDsn

    rabbit_mq_broker_url: Optional[str] = None  # RabbitMQ URL pointing to a running server (if none - disables pub/sub)


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    return AppSettings()  # type: ignore  [call-arg]


settings = generate_settings()
