from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.types import (
    AccumulationBehaviourType,
    DataQualifierType,
    FlowDirectionType,
    KindType,
    PhaseCode,
    QualityFlagsType,
    RoleFlagsType,
    UomType,
)
from sqlalchemy import INTEGER, VARCHAR, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

import envoy.server.model as original_models
from envoy.server.model.archive import ArchiveBase
from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX


class ArchiveSiteReadingType(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.site_reading.SiteReadingType.__tablename__  # type: ignore

    site_reading_type_id: Mapped[int] = mapped_column(INTEGER, index=True)
    aggregator_id: Mapped[int] = mapped_column(INTEGER)
    site_id: Mapped[int] = mapped_column(INTEGER)
    mrid: Mapped[str] = mapped_column(VARCHAR(length=32, collation="case_insensitive"))
    group_id: Mapped[int] = mapped_column(INTEGER)
    group_mrid: Mapped[str] = mapped_column(VARCHAR(length=32, collation="case_insensitive"))
    uom: Mapped[UomType] = mapped_column(INTEGER)
    data_qualifier: Mapped[DataQualifierType] = mapped_column(INTEGER)
    flow_direction: Mapped[FlowDirectionType] = mapped_column(INTEGER)
    accumulation_behaviour: Mapped[AccumulationBehaviourType] = mapped_column(INTEGER)
    kind: Mapped[KindType] = mapped_column(INTEGER)
    phase: Mapped[PhaseCode] = mapped_column(INTEGER)
    power_of_ten_multiplier: Mapped[int] = mapped_column(INTEGER)
    default_interval_seconds: Mapped[int] = mapped_column(INTEGER)
    role_flags: Mapped[RoleFlagsType] = mapped_column(INTEGER)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the reading set was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the reading set was last altered


class ArchiveSiteReading(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.site_reading.SiteReading.__tablename__  # type: ignore

    site_reading_id: Mapped[int] = mapped_column(BigInteger, index=True)
    site_reading_type_id: Mapped[int] = mapped_column(INTEGER)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    local_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    quality_flags: Mapped[QualityFlagsType] = mapped_column(INTEGER)
    time_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    time_period_seconds: Mapped[int] = mapped_column(INTEGER)  # Length of the reading in seconds
    value: Mapped[int] = mapped_column(
        BigInteger
    )  # actual reading value - type/power of ten are defined in the parent reading set
