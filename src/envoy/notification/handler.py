import logging
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from fastapi import FastAPI
from taskiq import AsyncBroker, InMemoryBroker, SimpleRetryMiddleware
from taskiq.result_backends.dummy import DummyResultBackend
from taskiq_aio_pika import AioPikaBroker  # type: ignore # https://github.com/taskiq-python/taskiq-aio-pika/pull/28

logger = logging.getLogger(__name__)

# This is a bit of a cludge for testing. Normally this won't be set in a production environment
#
# Reference to the shared InMemoryBroker. Will be lazily instantiated
ENABLED_IN_MEMORY_BROKER: Optional[InMemoryBroker] = None


# The currently enabled broker (if any). Will point to the last broker instantiated by enable_notification_workers
# This will normally NOT be available at import time for the purposes of decorating task functions
#
# So task functions should annotated using:
# @async_shared_broker.task()
# async def my_task(p1: int) -> None:
#   await sleep(p1)
#   print("Hello World")
#
# And then kicked using:
#   await my_task.kicker().with_broker(enabled_broker).kiq(1)
enabled_broker: Optional[AsyncBroker] = None


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

    global enabled_broker
    enabled_broker = broker
    return context_manager
