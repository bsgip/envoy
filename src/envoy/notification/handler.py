import logging
import ssl
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import AsyncBroker, Context, InMemoryBroker, SimpleRetryMiddleware, TaskiqDepends
from taskiq.result_backends.dummy import DummyResultBackend
from taskiq_aio_pika import AioPikaBroker

logger = logging.getLogger(__name__)

# TaskIQ state key for a function that when executed will return a new AsyncSession
STATE_DB_SESSION_MAKER = "db_session_maker"
# TaskIQ state key for an optional string
STATE_HREF_PREFIX = "href_prefix"
# TaskIQ state key for the prebuilt httpx "verify" argument used on outbound notification requests. This is either a
# bool (standard TLS verification toggle) or a reusable SSLContext holding the mTLS client certificate (built once at
# WORKER_STARTUP so the certificate files are only read from disk on worker startup)
STATE_TLS_VERIFY = "tls_verify"


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


# Reference to the shared InMemoryBroker. Will be lazily instantiated
ENABLED_IN_MEMORY_BROKER: InMemoryBroker | None = None


_enabled_broker: AsyncBroker | None = None


def get_enabled_broker() -> AsyncBroker | None:
    """The currently enabled broker (if any). Will point to the last broker instantiated by enable_notification_workers
    This will normally NOT be available at import time for the purposes of decorating task functions

    So task functions should annotated using:
    @async_shared_broker.task()
    async def my_task(p1: int) -> None:
      await sleep(p1)
      print("Hello World")

    And then kicked using:
      await my_task.kicker().with_broker(enabled_broker).kiq(1)"""
    return _enabled_broker


def generate_broker(rabbit_mq_broker_url: str | None) -> AsyncBroker:
    """Creates a AsyncBroker for the specified config (startup/shutdown will not initialised)"""

    use_rabbit_mq = bool(rabbit_mq_broker_url)
    logging.info(f"Generating Broker - Using Rabbit MQ: {use_rabbit_mq}")

    if use_rabbit_mq:
        return AioPikaBroker(url=rabbit_mq_broker_url, result_backend=DummyResultBackend()).with_middlewares(
            SimpleRetryMiddleware(default_retry_count=2)  # This will only save us from uncaught exceptions
        )
    else:
        # If we are using InMemory - lets keep the same reference going for all instances
        global ENABLED_IN_MEMORY_BROKER
        if ENABLED_IN_MEMORY_BROKER is not None:
            return ENABLED_IN_MEMORY_BROKER
        else:
            ENABLED_IN_MEMORY_BROKER = InMemoryBroker()
            return ENABLED_IN_MEMORY_BROKER


def enable_notification_client(
    rabbit_mq_broker_url: str | None,
) -> Callable[[FastAPI], _AsyncGeneratorContextManager]:
    """If executed - will generate a context manager (compatible with FastAPI lifetime managers) that when installed
    will (on app startup) enable the async notification client

    rabbit_mq_broker_url - If set - use RabbitMQ to broker notifications, otherwise InMemoryBroker will be used

    Return return value can be passed right into a FastAPI context manager with:
    lifespan_manager = enable_notification_workers(...)
    app = FastAPI(lifespan=lifespan_manager)
    """
    broker = generate_broker(rabbit_mq_broker_url)

    @asynccontextmanager
    async def context_manager(app: FastAPI) -> AsyncIterator:
        """This context manager will perform all setup before yield and teardown after yield"""

        await broker.startup()

        yield

        await broker.shutdown()

    global _enabled_broker
    _enabled_broker = broker
    return context_manager


async def broker_dependency(context: Annotated[Context, TaskiqDepends()]) -> AsyncBroker:
    return context.broker


async def href_prefix_dependency(context: Annotated[Context, TaskiqDepends()]) -> str | None:
    return getattr(context.state, STATE_HREF_PREFIX, None)


async def tls_verify_dependency(context: Annotated[Context, TaskiqDepends()]) -> ssl.SSLContext | bool:
    return getattr(context.state, STATE_TLS_VERIFY, True)


async def session_dependency(context: Annotated[Context, TaskiqDepends()]) -> AsyncGenerator[AsyncSession, None]:
    """Yields a session from TaskIq context session maker (maker created during WORKER_STARTUP event) and
    then closes it after shutdown"""
    session_maker = getattr(context.state, STATE_DB_SESSION_MAKER)
    session: AsyncSession = session_maker()

    try:
        yield session
    except Exception as exc:
        logger.error("Uncaught exception. Attempting to roll back session gracefully", exc_info=exc)
        await session.rollback()
    await session.close()
