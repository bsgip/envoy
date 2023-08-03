from sqlalchemy import event
from sqlalchemy.engine import Engine

from envoy.server.api.auth.azure import AzureADResourceTokenConfig, update_azure_ad_token_cache
from envoy.server.cache import AsyncCache


def enable_dynamic_azure_ad_database_credentials(tenant_id: str, client_id: str, valid_issuer: str, resource_id: str):
    """If executed - will enable a SQLAlchemy event listener that will dynamically rewrite new DB connections
    to use an Azure AD token for the specified database resource"""

    # Create the cache - force it to update
    cache: AsyncCache[str, str] = AsyncCache(update_fn=update_azure_ad_token_cache)
    cfg = AzureADResourceTokenConfig(
        tenant_id=tenant_id, client_id=client_id, valid_issuer=valid_issuer, resource_id=resource_id
    )
    cache.get_value_sync(cfg, cfg.resource_id)

    # SQLAlchemy events do NOT support async so we need to perform some shenanigans to keep this running
    def dynamic_db_do_connect_listener(dialect, conn_rec, cargs, cparams):
        """Designed to listen for the Engine do_connect event and update cargs with the latest cached"""
        resource_pwd = cache.get_value_sync(cfg, cfg.resource_id)
        cparams["password"] = resource_pwd

    event.listen(Engine, "do_connect", dynamic_db_do_connect_listener)
