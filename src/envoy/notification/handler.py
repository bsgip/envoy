import logging
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import Annotated, AsyncGenerator, AsyncIterator, Callable, Optional

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import AsyncBroker, Context, InMemoryBroker, SimpleRetryMiddleware, TaskiqDepends
from taskiq.result_backends.dummy import DummyResultBackend
from taskiq_aio_pika import AioPikaBroker  # type: ignore # https://github.com/taskiq-python/taskiq-aio-pika/pull/28

logger = logging.getLogger(__name__)

# TaskIQ state key for a function that when executed will return a new AsyncSession
STATE_DB_SESSION_MAKER = "db_session_maker"
# TaskIQ state key for an optional string
STATE_HREF_PREFIX = "href_prefix"


# Reference to the shared InMemoryBroker. Will be lazily instantiated
ENABLED_IN_MEMORY_BROKER: Optional[InMemoryBroker] = None


_enabled_broker: Optional[AsyncBroker] = None


def get_enabled_broker() -> Optional[AsyncBroker]:
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


def generate_broker(rabbit_mq_broker_url: Optional[str]) -> AsyncBroker:
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
    rabbit_mq_broker_url: Optional[str],
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


async def href_prefix_dependency(context: Annotated[Context, TaskiqDepends()]) -> Optional[str]:
    return getattr(context.state, STATE_HREF_PREFIX, None)


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
