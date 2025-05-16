from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, INTEGER, BigInteger, DateTime, Index
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
    randomize_start_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    import_limit_active_watts: Mapped[Decimal] = mapped_column(DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES))
    export_limit_watts: Mapped[Decimal] = mapped_column(DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES))

    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # NOTE: We've decided to include these 'non-DOE' related fields (that map to DERControl elements) here and
    # eventually completely drop the DOE concept and convert this entity to reflect the CSIP-AUS DERControl resource.
    generation_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )
    load_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )
    set_energized: Mapped[Optional[bool]] = mapped_column(nullable=True)
    set_connected: Mapped[Optional[bool]] = mapped_column(nullable=True)

    __table_args__ = (
        Index(
            "archive_doe_end_time_deleted_time_site_id", "end_time", "deleted_time", "site_id"
        ),  # This is to support finding DOE's that have been deleted (or cancelled)
    )
