from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BOOLEAN, DECIMAL, INTEGER, VARCHAR, BigInteger, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

import envoy.server.model as original_models
from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX, ArchiveBase


class ArchiveSiteControlGroup(ArchiveBase):
    """Represents a top level grouping of controls. The grouping is NOT site scoped but the underlying controls will be

    A group contains metadata and a "primacy" to distinguish it's controls from other SiteControlGroups"""

    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.doe.SiteControlGroup.__tablename__  # type: ignore

    site_control_group_id: Mapped[int] = mapped_column(INTEGER, index=True)
    description: Mapped[str] = mapped_column(VARCHAR(length=32))
    primacy: Mapped[int] = mapped_column(INTEGER)
    fsa_id: Mapped[int] = mapped_column(INTEGER)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArchiveDynamicOperatingEnvelope(ArchiveBase):
    """Represents a dynamic operating envelope for a site at a particular time interval"""

    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.doe.DynamicOperatingEnvelope.__tablename__  # type: ignore
    dynamic_operating_envelope_id: Mapped[int] = mapped_column(BigInteger, index=True)
    site_control_group_id: Mapped[int] = mapped_column(INTEGER)
    site_id: Mapped[int] = mapped_column(INTEGER)
    calculation_log_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column()
    randomize_start_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    import_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )
    export_limit_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )

    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    superseded: Mapped[bool] = mapped_column(BOOLEAN)

    generation_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )
    load_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )
    set_energized: Mapped[Optional[bool]] = mapped_column(nullable=True)
    set_connected: Mapped[Optional[bool]] = mapped_column(nullable=True)
    set_point_percentage: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )
    ramp_time_seconds: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, original_models.doe.DOE_DECIMAL_PLACES), nullable=True
    )

    __table_args__ = (
        Index(
            "archive_doe_site_control_group_id_end_time_deleted_time_site_id",
            "site_control_group_id",
            "end_time",
            "deleted_time",
            "site_id",
        ),  # This is to support finding DOE's that have been deleted (or cancelled)
    )
