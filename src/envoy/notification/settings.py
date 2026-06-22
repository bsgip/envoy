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

    notification_poll_seconds: float = 3  # How long the worker sleeps between polls when the queues are empty
    notification_check_batch_size: int = 10  # Max notification_check rows claimed per worker cycle
    notification_transmit_batch_size: int = 20  # Max notification_transmit rows claimed (and sent) per worker cycle


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    return AppSettings()  # ty:ignore[missing-argument]


settings = generate_settings()
