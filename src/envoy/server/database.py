import logging
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI
from sqlalchemy import Dialect, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import ConnectionPoolEntry

from envoy.server.api.auth.azure import AzureADResourceTokenConfig, update_azure_ad_token_cache
from envoy.server.cache import AsyncCache
from envoy.server.tasks import repeat_every

logger = logging.getLogger(__name__)


@dataclass
class HandlerDetails:
    sql_alchemy_connect_handler: Callable


async def install_handler(cfg: AzureADResourceTokenConfig, manual_update_frequency_seconds: int) -> HandlerDetails:
    """Lower level version of enable_dynamic_azure_ad_database_credentials that directly installs
    the connection rewriting without wrapping it in a context manager"""
    cache: AsyncCache[str, str] = AsyncCache(update_fn=update_azure_ad_token_cache)

    # SQLAlchemy events do NOT support async so we need to perform some shenanigans to keep this running
    # We will use the cache.get_value_sync to fetch tokens and update_cache_Task to ensure they always remain
    # current.
    def dynamic_db_do_connect_listener(
        dialect: Dialect, conn_rec: ConnectionPoolEntry, cargs: tuple[Any, ...], cparams: dict
    ) -> None:
        """Designed to listen for the Engine do_connect event and update cargs with the latest cached"""
        resource_pwd = cache.get_value_sync(cfg, cfg.resource_id)
        cparams["password"] = resource_pwd

    event.listen(Engine, "do_connect", dynamic_db_do_connect_listener)

    @repeat_every(seconds=manual_update_frequency_seconds)
    async def update_cache_task() -> None:
        """This will manually update the DB token cache on a regular schedule. It's necessary as the get_value_sync
        might potentially miss an expiry in the event that we receive no token requests for an extended period of
        time.

        The aim is to keep well ahead of the token expiry so that the cache.get_value_sync never has to trigger an
        update and only exists as a fallback mechanism"""
        logging.info(f"update_cache_task for database token. next in {manual_update_frequency_seconds} seconds")
        await cache.force_update(cfg)

    # force our cache our background tasks to start triggering
    await update_cache_task()

    return HandlerDetails(sql_alchemy_connect_handler=dynamic_db_do_connect_listener)


async def remove_handler(handler_details: HandlerDetails) -> None:
    """Given the returned value from install_handler: deregister the event handlers performing the Azure AD
    connection rewriting"""
    event.remove(Engine, "do_connect", handler_details.sql_alchemy_connect_handler)


def enable_dynamic_azure_ad_database_credentials(
    tenant_id: str,
    client_id: str,
    resource_id: str,
    manual_update_frequency_seconds: int,
) -> Callable[[FastAPI], _AsyncGeneratorContextManager]:
    """If executed - will generate a context manager (compatible with FastAPI lifetime managers) that when installed
    will (on app startup) create an SQLAlchemy event listener that will dynamically rewrite new DB connections
    to use an Azure AD token for the specified database resource.

    Background tasks will be set to permanently run that will ensure that the tokens always remain up to date w.r.t
    to their expiry.

    tenant_id: The Azure AD tenant ID that this app is running in
    client_id: The Azure AD client ID of this app/VM
    resource_id: The Azure AD resource ID of the database service to generate tokens for
    manual_update_frequency_seconds: The time in seconds between manual cache refreshes (should be < token expiry)

    Return return value can be passed right into a FastAPI context manager with:
    lifespan_manager = enable_dynamic_azure_ad_database_credentials(...)
    app = FastAPI(lifespan=lifespan_manager)
    """

    logging.info(f"Enabling dynamic database creds for {resource_id} at frequency {manual_update_frequency_seconds}")
    cfg = AzureADResourceTokenConfig(tenant_id=tenant_id, client_id=client_id, resource_id=resource_id)

    @asynccontextmanager
    async def context_manager(app: FastAPI) -> AsyncIterator:
        """This context manager will perform all setup before yield and teardown after yield"""

        handler = await install_handler(cfg, manual_update_frequency_seconds)

        yield  # Code after this will execute during app shutdown

        await remove_handler(handler)

    return context_manager
