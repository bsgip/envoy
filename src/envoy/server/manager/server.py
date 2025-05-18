from dataclasses import asdict, replace
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.server import select_server_config
from envoy.server.model.config.server import RuntimeServerConfig
from envoy.server.model.server import RuntimeServerConfig as ConfigEntity

# reference default values
default = RuntimeServerConfig()


# NOTE: Too simple so decided to skip mapping layer
def _map_server_config(
    live_config: Optional[ConfigEntity],
) -> RuntimeServerConfig:
    if not live_config:
        return default

    # extract expected fields from domain model
    cfg_fields = asdict(default).keys()

    live_values = {
        field: getattr(live_config, field) for field in cfg_fields if getattr(live_config, field) is not None
    }

    # return new instance with non-null values from entity replacing those in default
    return replace(default, **live_values)


class RuntimeServerConfigManager:
    @staticmethod
    async def fetch_current_config(session: AsyncSession) -> RuntimeServerConfig:
        """Fetches the current config (with any defaults applied for missing values)"""
        return _map_server_config(await select_server_config(session))
