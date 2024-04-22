from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.types import (
    AccumulationBehaviourType,
    DataQualifierType,
    FlowDirectionType,
    KindType,
    PhaseCode,
    QualityFlagsType,
    UomType,
)
from sqlalchemy import INTEGER, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base, Site


class SiteReadingType(Base):
    """Aggregates SiteReading by the shared common data type (analogous to sep2 ReadingType)."""

    __tablename__ = "site_reading_type"

    site_reading_type_id: Mapped[int] = mapped_column(primary_key=True)
    aggregator_id: Mapped[int] = mapped_column(
        ForeignKey("aggregator.aggregator_id")
    )  # Tracks aggregator at time of write
    site_id: Mapped[int] = mapped_column(
        ForeignKey("site.site_id")
    )  # Tracks the site that the underlying readings belong to

    # These and the above PK/FK all form the unique constraint
    uom: Mapped[UomType] = mapped_column(INTEGER)
    data_qualifier: Mapped[DataQualifierType] = mapped_column(INTEGER)
    flow_direction: Mapped[FlowDirectionType] = mapped_column(INTEGER)
    accumulation_behaviour: Mapped[AccumulationBehaviourType] = mapped_column(INTEGER)
    kind: Mapped[KindType] = mapped_column(INTEGER)
    phase: Mapped[PhaseCode] = mapped_column(INTEGER)
    power_of_ten_multiplier: Mapped[int] = mapped_column(INTEGER)
    default_interval_seconds: Mapped[int] = mapped_column(
        INTEGER
    )  # If a batch of readings is received without an interval - this length will be used to describe the batch length

    # These are the properties that can change via upsert
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the reading set was last altered

    site: Mapped["Site"] = relationship(lazy="raise")

    # We want to minimise duplicated reading types - we do this by essentially making the entire entity
    # into one big unique index
    __table_args__ = (
        UniqueConstraint(
            "aggregator_id",
            "site_id",
            "uom",
            "data_qualifier",
            "flow_direction",
            "accumulation_behaviour",
            "kind",
            "phase",
            "power_of_ten_multiplier",
            "default_interval_seconds",
            name="site_reading_type_all_values_uc",
        ),
    )


class SiteReading(Base):
    """The actual underlying time and value readings. These are explicitly kept 'thin' as this table will receive a
    mountain of rows"""

    __tablename__ = "site_reading"

    site_reading_id: Mapped[int] = mapped_column(primary_key=True)
    site_reading_type_id: Mapped[int] = mapped_column(ForeignKey("site_reading_type.site_reading_type_id"))
    changed_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # When the reading was last altered

    local_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)  # Internal id assigned by aggregator
    quality_flags: Mapped[QualityFlagsType] = mapped_column(INTEGER)
    time_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the reading starts
    time_period_seconds: Mapped[int] = mapped_column(INTEGER)  # Length of the reading in seconds
    value: Mapped[int] = mapped_column(
        BigInteger
    )  # actual reading value - type/power of ten are defined in the parent reading set

    site_reading_type: Mapped["SiteReadingType"] = relationship(lazy="raise")

    __table_args__ = (
        UniqueConstraint("site_reading_type_id", "time_period_start", name="site_reading_type_id_time_period_start_uc"),
    )
