import logging
from typing import Annotated, AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from taskiq import Context, TaskiqDepends, TaskiqEvents, TaskiqState

from envoy.notification.handler import generate_broker
from envoy.notification.settings import generate_settings
from envoy.server.api.auth.azure import AzureADResourceTokenConfig
from envoy.server.database import HandlerDetails, install_handler, remove_handler

logger = logging.getLogger(__name__)


logger.info("Initialising Notification TaskIQ Worker")

settings = generate_settings()
broker = generate_broker(settings.rabbit_mq_broker_url)


async def session_dependency(context: Annotated[Context, TaskiqDepends()]) -> AsyncGenerator[AsyncSession, None]:
    """Yields a session from TaskIq context session maker (maker created during WORKER_STARTUP event) and
    then closes it after shutdown"""
    session: AsyncSession = context.state.db_session_maker()
    yield session
    await session.close()


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
