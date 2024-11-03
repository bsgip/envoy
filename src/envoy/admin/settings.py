import importlib.metadata
from typing import Any, Dict

from envoy.settings import CommonSettings


class AppSettings(CommonSettings):
    model_config = {"validate_assignment": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    debug: bool = False
    docs_url: str = "/docs"
    openapi_prefix: str = ""
    openapi_url: str = "/openapi.json"
    redoc_url: str = "/redoc"
    title: str = "envoy-admin"
    version: str = importlib.metadata.version("envoy")

    admin_username: str
    admin_password: str

    read_only_user: str = "rouser"
    read_only_keys: list[str] = []  # Passwords that match with read_only_user and grant access to GET endpoints

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


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    # Silenced complaints about database_url - keeping mypy happy here is tricky (for certain python versions).
    # The "cost" of not having it set will be caught by our test coverage - this is an error we can ignore
    return AppSettings()  # type: ignore  [call-arg]


settings = generate_settings()
