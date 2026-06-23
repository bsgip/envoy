import json
import logging
import logging.config
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from taskiq import TaskiqEvents, TaskiqState

from envoy.notification.exception import NotificationError
from envoy.notification.handler import (
    STATE_DB_SESSION_MAKER,
    STATE_HREF_PREFIX,
    STATE_TLS_VERIFY,
    MtlsConfig,
    build_tls_verify,
    generate_broker,
)
from envoy.notification.settings import generate_settings
from envoy.server.api.auth.azure import AzureADResourceTokenConfig
from envoy.server.database import HandlerDetails, install_handler, remove_handler

# Force the loading of a LOG_CONFIG environment variable - it will be expecting a JSON encoded file
logging_config_file = os.environ.get("LOG_CONFIG", None)
if logging_config_file:
    try:
        with open(logging_config_file) as fp:
            logging_config = json.load(fp)
        logging.config.dictConfig(logging_config)
    except Exception:  # noqa: S110
        # Normally this would be very naughty - but a failure here is fine - just proceed as per normal
        # and failover whatever default logging is currently in place
        pass  # nosec

logger = logging.getLogger(__name__)

logger.info("Initialising Notification TaskIQ Worker")

settings = generate_settings()
broker = generate_broker(settings.rabbit_mq_broker_url)


# Now setup the lifecycle events for the worker
azure_ad_handler_details: HandlerDetails | None = None


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    global azure_ad_handler_details

    # Setup the AzureAD handler (if configured)
    if azure_ad_handler_details is not None:
        raise NotificationError("Startup issue - azure_ad_handler_details is already initialised")
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
    engine_args = db_cfg["engine_args"] if "engine_args" in db_cfg else {}
    db_engine = create_async_engine(db_cfg["db_url"], **engine_args)
    setattr(state, STATE_DB_SESSION_MAKER, async_sessionmaker(db_engine, expire_on_commit=False))
    setattr(state, STATE_HREF_PREFIX, settings.href_prefix)

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
    # Read the certificate files from disk into a reusable verify argument once, rather than per outbound request
    setattr(state, STATE_TLS_VERIFY, build_tls_verify(settings.notification_disable_tls_verify, mtls_config))


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    global azure_ad_handler_details

    if azure_ad_handler_details is not None:
        await remove_handler(azure_ad_handler_details)
        azure_ad_handler_details = None
