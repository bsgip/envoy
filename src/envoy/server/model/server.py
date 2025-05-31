from datetime import datetime
from typing import Optional

from sqlalchemy import BOOLEAN, INTEGER, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model.base import Base


class RuntimeServerConfig(Base):
    """Single row table for runtime server configurations, e.g. poll/post rates, for specific resources"""

    __tablename__ = "runtime_server_config"

    runtime_server_config_id: Mapped[int] = mapped_column(primary_key=True, default=1)

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the aggregator was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    dcap_pollrate_seconds: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)  # device capability
    edevl_pollrate_seconds: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)  # end device list
    fsal_pollrate_seconds: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)  # function set assignment list
    derpl_pollrate_seconds: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)  # der program list
    derl_pollrate_seconds: Mapped[Optional[int]] = mapped_column(
        INTEGER, nullable=True
    )  # der list + all associated der resources
    mup_postrate_seconds: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)  # mirror usage point
    site_control_pow10_encoding: Mapped[Optional[int]] = mapped_column(
        INTEGER, nullable=True
    )  # power of 10 encoding for site controls

    disable_edev_registration: Mapped[Optional[bool]] = mapped_column(
        BOOLEAN, nullable=True
    )  # Should EndDevice RegistrationLink's be disabled?
