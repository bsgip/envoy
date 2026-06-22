import logging
import ssl
from collections.abc import AsyncIterator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MtlsConfig:
    """Client certificate configuration for mTLS on outbound notification requests"""

    cert_path: str  # Path to client certificate PEM file
    key_path: str  # Path to client private key PEM file
    serca_path: str | None  # Path to SERCA PEM for verifying device server certs (None = system CAs)


def build_tls_verify(disable_tls_verify: bool, mtls_config: MtlsConfig | None) -> ssl.SSLContext | bool:
    """Builds the httpx "verify" argument for outbound notifications. With mTLS configured this reads the client
    certificate (and optional SERCA) from disk into a reusable SSLContext; otherwise returns a bool toggling standard
    TLS verification. Intended to be called once at worker startup so the certificate files are not re-read per request.
    """
    if mtls_config is None:
        return not disable_tls_verify

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_context.set_ciphers("ECDHE-ECDSA-AES128-CCM8:ALL:!aNULL")
    if disable_tls_verify:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    else:
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        if mtls_config.serca_path is not None:
            ssl_context.load_verify_locations(cafile=mtls_config.serca_path)
    ssl_context.load_cert_chain(certfile=mtls_config.cert_path, keyfile=mtls_config.key_path)
    return ssl_context


# Whether notifications are enabled in this process. Toggled by enable_notification_client at app startup/shutdown and
# consulted by NotificationManager to decide whether to enqueue notification checks.
_notifications_enabled: bool = False


def notifications_enabled() -> bool:
    """Returns True if notifications are enabled (i.e. NotificationManager should enqueue notification checks)"""
    return _notifications_enabled


def enable_notification_client() -> Callable[[FastAPI], _AsyncGeneratorContextManager]:
    """If executed - will generate a context manager (compatible with FastAPI lifetime managers) that marks
    notifications as enabled for the lifetime of the app. While enabled, NotificationManager enqueues notification
    checks (as part of the originating request's transaction) for the notification worker to process.

    Return value can be passed right into a FastAPI context manager with:
    lifespan_manager = enable_notification_client()
    app = FastAPI(lifespan=lifespan_manager)
    """

    @asynccontextmanager
    async def context_manager(app: FastAPI) -> AsyncIterator:
        global _notifications_enabled
        _notifications_enabled = True
        try:
            yield
        finally:
            _notifications_enabled = False

    return context_manager
