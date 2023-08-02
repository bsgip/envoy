import asyncio

from sqlalchemy import event
from sqlalchemy.engine import Engine

from envoy.server.api.auth.azure import AzureADResourceTokenConfig, update_azure_ad_token_cache
from envoy.server.cache import AsyncCache


def enable_dynamic_azure_ad_database_credentials(tenant_id: str, client_id: str, valid_issuer: str, resource_id: str):
    """If executed - will enable a SQLAlchemy event listener that will dynamically rewrite new DB connections
    to use an Azure AD token for the specified database resource"""

    cache: AsyncCache[str, str] = AsyncCache(update_fn=update_azure_ad_token_cache)
    cfg = AzureADResourceTokenConfig(
        tenant_id=tenant_id, client_id=client_id, valid_issuer=valid_issuer, resource_id=resource_id
    )

    def dynamic_db_do_connect_listener(dialect, conn_rec, cargs, cparams):
        """Designed to listen for the Engine do_connect event and update cargs with the latest cached"""
        print(f"cargs {cargs}")
        print(f"cparams {cparams}")
        password = asyncio.run(cache.get_value(cfg, cfg.resource_id))
        cargs["password"] = password

    event.listen(Engine, "do_connect", dynamic_db_do_connect_listener)
