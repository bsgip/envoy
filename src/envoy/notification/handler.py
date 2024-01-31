import logging
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from fastapi import FastAPI
from taskiq import InMemoryBroker
from taskiq.result_backends.dummy import DummyResultBackend
from taskiq_aio_pika import AioPikaBroker

logger = logging.getLogger(__name__)


def enable_notification_workers(
    rabbit_mq_broker_url: Optional[str],
) -> Callable[[FastAPI], _AsyncGeneratorContextManager]:
    """If executed - will generate a context manager (compatible with FastAPI lifetime managers) that when installed
    will (on app startup) enable the async notification workers

    rabbit_mq_broker_url - If set - use RabbitMQ to broker notifications, otherwise InMemoryBroker will be used

    Return return value can be passed right into a FastAPI context manager with:
    lifespan_manager = enable_dynamic_azure_ad_database_credentials(...)
    app = FastAPI(lifespan=lifespan_manager)
    """

    use_rabbit_mq = bool(rabbit_mq_broker_url)
    logging.info(f"Enabling notification workers - Using Rabbit MQ: {use_rabbit_mq}")

    if use_rabbit_mq:
        broker = AioPikaBroker(url=rabbit_mq_broker_url, result_backend=DummyResultBackend())
    else:
        broker = InMemoryBroker()

    @asynccontextmanager
    async def context_manager(app: FastAPI) -> AsyncIterator:
        """This context manager will perform all setup before yield and teardown after yield"""

        await broker.startup()

        yield

        await broker.shutdown()

    return context_manager
