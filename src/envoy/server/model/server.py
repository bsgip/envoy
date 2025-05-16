from datetime import datetime
from typing import Optional

from sqlalchemy import func, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model.base import Base
from envoy.server.model.config.server import RuntimeServerConfig as AppRuntimeServerConfig


class RuntimeServerConfig(Base):
    """Single row table for runtime server configurations e.g. poll/post rates for specific resources"""

    __tablename__ = "runtime_server_config"

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the aggregator was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    dcap_pollrate_seconds: Optional[int]
    edevl_pollrate_seconds: Optional[int]
    fsal_pollrate_seconds: Optional[int]
    derpl_pollrate_seconds: Optional[int]
    derl_pollrate_seconds: Optional[int]
    mup_postrate_seconds: Optional[int]


# NOTE: Too simple to have dedicated manager, mapper, etc.
def map_server_config(live_server_config: Optional[RuntimeServerConfig] = None) -> AppRuntimeServerConfig:
    if live_server_config:
        return AppRuntimeServerConfig(
            dcap_pollrate_seconds=live_server_config.dcap_pollrate_seconds
            or AppRuntimeServerConfig.dcap_pollrate_seconds,
            edevl_pollrate_seconds=live_server_config.edevl_pollrate_seconds,
            fsal_pollrate_seconds=live_server_config.fsal_pollrate_seconds,
            derpl_pollrate_seconds=live_server_config.derpl_pollrate_seconds,
            derl_pollrate_seconds=live_server_config.derl_pollrate_seconds,
            mup_postrate_seconds=live_server_config.mup_postrate_seconds,
        )

    return AppRuntimeServerConfig()
