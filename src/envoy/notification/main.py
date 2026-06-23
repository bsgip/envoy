import asyncio
import logging
import ssl
from collections.abc import AsyncIterator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from envoy.notification.exception import NotificationError
from envoy.notification.handler import MtlsConfig, build_tls_verify
from envoy.notification.settings import AppSettings, generate_settings
from envoy.notification.task.check import process_check_batch
from envoy.notification.task.transmit import process_transmit_batch

logger = logging.getLogger(__name__)


def resolve_tls_verify(settings: AppSettings) -> ssl.SSLContext | bool:
    """Reads the (optional) outbound mTLS certificate config from settings into a reusable httpx "verify" argument.
    Intended to be called once at worker startup so the certificate files are not re-read per request."""
    mtls_config: MtlsConfig | None = None
    if settings.notifications_with_mtls:
        if not settings.notification_mtls_cert or not settings.notification_mtls_key:
            raise NotificationError(
                "NOTIFICATIONS_WITH_MTLS is enabled but NOTIFICATION_MTLS_CERT + NOTIFICATION_MTLS_KEY must both be set"
            )
        mtls_config = MtlsConfig(
            cert_path=settings.notification_mtls_cert,
            key_path=settings.notification_mtls_key,
            serca_path=settings.notification_mtls_serca,
        )
    return build_tls_verify(settings.notification_disable_tls_verify, mtls_config)


async def run_poll_loop(
    session_maker: async_sessionmaker[AsyncSession],
    tls_verify: ssl.SSLContext | bool,
    settings: AppSettings,
    stop_event: asyncio.Event,
) -> None:
    """The notification worker loop. Each cycle drains pending notification_check rows (fanning them out into
    notification_transmit rows) then sends due transmissions; it keeps draining while there is work and otherwise
    sleeps for notification_poll_seconds. Runs until stop_event is set."""
    logger.info("Notification worker started")
    while not stop_event.is_set():
        try:
            checks = await process_check_batch(
                session_maker, settings.href_prefix, settings.notification_check_batch_size
            )
            transmits = await process_transmit_batch(
                session_maker, tls_verify, settings.notification_transmit_batch_size
            )
        except Exception as exc:
            logger.error("Unexpected exception in notification worker cycle", exc_info=exc)
            checks = transmits = 0

        # Keep draining while there's work to do, otherwise wait for the next poll (or an early stop)
        if checks == 0 and transmits == 0:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.notification_poll_seconds)
            except TimeoutError:
                pass
    logger.info("Notification worker stopped")


def enable_notification_worker(db_kwargs: dict[str, Any]) -> Callable[[FastAPI], _AsyncGeneratorContextManager]:
    """Returns a FastAPI lifespan context manager that runs the notification worker in-process as a background task
    (started on app startup, stopped on shutdown) - draining the notification_check / notification_transmit queue
    tables and delivering notifications.

    db_kwargs - The db_middleware_kwargs (db_url + optional engine_args) used to build the worker's session maker."""
    settings = generate_settings()
    engine_args = db_kwargs.get("engine_args", {})
    engine = create_async_engine(db_kwargs["db_url"], **engine_args)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    tls_verify = resolve_tls_verify(settings)

    @asynccontextmanager
    async def context_manager(app: FastAPI) -> AsyncIterator:
        stop_event = asyncio.Event()
        task = asyncio.create_task(run_poll_loop(session_maker, tls_verify, settings, stop_event))
        try:
            yield
        finally:
            stop_event.set()
            await task
            await engine.dispose()

    return context_manager
