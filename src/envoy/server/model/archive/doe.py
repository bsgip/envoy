from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, INTEGER, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

import envoy.server.model as original_models
from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX, ArchiveBase


class ArchiveDynamicOperatingEnvelope(ArchiveBase):
    """Represents a dynamic operating envelope for a site at a particular time interval"""

    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.doe.DynamicOperatingEnvelope.__tablename__  # type: ignore
    dynamic_operating_envelope_id: Mapped[int] = mapped_column(BigInteger, index=True)
    site_id: Mapped[int] = mapped_column(INTEGER)
    calculation_log_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column()
    import_limit_active_watts: Mapped[Decimal] = mapped_column(DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES))
    export_limit_watts: Mapped[Decimal] = mapped_column(DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES))
