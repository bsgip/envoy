from datetime import datetime
from typing import Optional

from sqlalchemy import func, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model.base import Base


class DynamicServerConfiguration(Base):
    """Single row table for runtime server configurations e.g. poll/post rates for specific resources"""

    __tablename__ = "dynamic_server_configuration"

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
