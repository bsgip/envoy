import importlib.metadata

from envoy.settings import CommonSettings


class AppSettings(CommonSettings):
    model_config = {"validate_assignment": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    title: str = "envoy-notifications"
    version: str = importlib.metadata.version("envoy")

    notification_disable_tls_verify: bool = False  # Disable TLS cert verification for outbound notifications
    notifications_with_mtls: bool = False  # Present a client certificate on outbound notification requests
    notification_mtls_cert: str | None = None  # Path to client certificate PEM for outbound mTLS
    notification_mtls_key: str | None = None  # Path to client private key PEM for outbound mTLS
    notification_mtls_serca: str | None = (
        None  # Path to SERCA PEM for verifying device server certs (None = system CAs)
    )


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    return AppSettings()  # ty:ignore[missing-argument]


settings = generate_settings()
