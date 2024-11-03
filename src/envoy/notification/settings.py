import importlib.metadata

from envoy.settings import CommonSettings


class AppSettings(CommonSettings):
    model_config = {"validate_assignment": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    title: str = "envoy-notifications"
    version: str = importlib.metadata.version("envoy")


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    return AppSettings()  # type: ignore  [call-arg]


settings = generate_settings()
