import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from taskiq import TaskiqEvents, TaskiqState

from envoy.notification.handler import generate_broker
from envoy.notification.settings import generate_settings
from envoy.server.api.auth.azure import AzureADResourceTokenConfig
from envoy.server.database import HandlerDetails, install_handler, remove_handler

logger = logging.getLogger(__name__)


logger.info("Initialising Notification TaskIQ Worker")
settings = generate_settings()


async def session_dependency() -> AsyncGenerator[AsyncSession, None]:
    print("Startup")
    await asyncio.sleep(0.1)

    yield "value"

    await asyncio.sleep(0.1)
    print("Shutdown")


broker = generate_broker(settings.rabbit_mq_broker_url)

# Now setup the lifecycle events for the worker
azure_ad_handler_details: Optional[HandlerDetails] = None


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    global azure_ad_handler_details

    # Setup the AzureAD handler (if configured)
    if azure_ad_handler_details is not None:
        raise Exception("Startup issue - azure_ad_handler_details is already initialised")
    azure_ad_settings = settings.azure_ad_kwargs
    if azure_ad_settings and settings.azure_ad_db_resource_id:
        logger.info(f"Enabling AzureADAuth: {azure_ad_settings}")

        ad_config = AzureADResourceTokenConfig(
            tenant_id=azure_ad_settings["tenant_id"],
            client_id=azure_ad_settings["client_id"],
            resource_id=settings.azure_ad_db_resource_id,
        )
        azure_ad_handler_details = await install_handler(ad_config, settings.azure_ad_db_refresh_secs)

    # Setup the database session maker
    db_cfg = settings.db_middleware_kwargs
    db_engine = create_async_engine(db_cfg["db_url"], **db_cfg["engine_args"])
    state.db_session_maker = async_sessionmaker(db_engine, expire_on_commit=False)


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    global azure_ad_handler_details

    if azure_ad_handler_details is not None:
        await remove_handler(azure_ad_handler_details)
        azure_ad_handler_details = None
