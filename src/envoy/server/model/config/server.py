from dataclasses import dataclass, asdict, replace
from typing import Optional

from envoy.server.model import server


@dataclass(slots=True, frozen=True)
class DynamicServerConfiguration:
    """Internal Domain model that represents runtime server configurations that can be varied dynamically."""

    dcap_pollrate_seconds: int = 300
    edevl_pollrate_seconds: int = 300
    fsal_pollrate_seconds: int = 300
    derpl_pollrate_seconds: int = 60
    derl_pollrate_seconds: int = 60
    mup_postrate_seconds: int = 60


# reference default values
default = DynamicServerConfiguration()


# NOTE: Too simple to have dedicated manager, mapper, etc.
def map_server_config(
    live_config: Optional[server.DynamicServerConfiguration] = None,
) -> DynamicServerConfiguration:
    if not live_config:
        return default

    # extract expected fields from domain model
    cfg_fields = asdict(default).keys()

    live_values = {
        field: getattr(live_config, field) for field in cfg_fields if getattr(live_config, field) is not None
    }

    # return new instance with non-null values from entity replacing those in default
    return replace(default, **live_values)
