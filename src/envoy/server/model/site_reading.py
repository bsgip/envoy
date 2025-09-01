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
from sqlalchemy import INTEGER, VARCHAR, BigInteger, DateTime, ForeignKey, Index, Sequence, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base, Site

# Used for creating unique values for SiteReadingType.group_id as required
# We could've done this via a parent table group but it would just be unnecessary overhead
# This is the most lightweight way of implementing it
SITE_READING_TYPE_GROUP_ID_SEQUENCE = Sequence("site_reading_type_group_id_seq")


class SiteReadingType(Base):
    """Aggregates SiteReading by the shared common data type (analogous to sep2 MirrorMeterReading/ReadingType)."""

    __tablename__ = "site_reading_type"

    site_reading_type_id: Mapped[int] = mapped_column(primary_key=True)
    aggregator_id: Mapped[int] = mapped_column(
        ForeignKey("aggregator.aggregator_id")
    )  # Tracks aggregator at time of write
    site_id: Mapped[int] = mapped_column(
        ForeignKey("site.site_id")
    )  # Tracks the site that the underlying readings belong to
    mrid: Mapped[str] = mapped_column(
        VARCHAR(length=32, collation="case_insensitive")
    )  # hex string (should be case insensitive). Uniquely identifies this SiteReadingType for a specific site
    # NOTE: The case_insensitive collation is managed manually in the alembic migration "add_ci_lfdis"
    group_id: Mapped[int] = mapped_column(INTEGER)  # Means for virtually grouping this entity under a MUP
    group_mrid: Mapped[str] = mapped_column(
        VARCHAR(length=32, collation="case_insensitive")
    )  # hex string (should be case insensitive). Uniquely identifies the parent MUP
    # NOTE: The case_insensitive collation is managed manually in the alembic migration "add_ci_lfdis"

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
    role_flags: Mapped[RoleFlagsType] = mapped_column(INTEGER)

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the reading set was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the reading set was last altered

    site: Mapped["Site"] = relationship(lazy="raise")

    # Uniqueness is managed by the client controlled mrid
    __table_args__ = (
        UniqueConstraint(
            "aggregator_id",
            "site_id",
            "mrid",
            name="site_reading_type_aggregator_id_site_id_mrid_uc",
        ),
        Index(
            "site_reading_type_aggregator_id_group_mrid_ix", "aggregator_id", "group_mrid", unique=False
        ),  # To support aggregator cert lookups
        Index(
            "site_reading_type_aggregator_id_group_id_ix", "aggregator_id", "group_id", unique=False
        ),  # To support aggregator cert lookups
        Index(
            "site_reading_type_aggregator_id_site_id_group_id_ix", "aggregator_id", "site_id", "group_id", unique=False
        ),  # To support device cert lookups
    )


class SiteReading(Base):
    """The actual underlying time and value readings. These are explicitly kept 'thin' as this table will receive a
    mountain of rows"""

    __tablename__ = "site_reading"

    site_reading_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_reading_type_id: Mapped[int] = mapped_column(ForeignKey("site_reading_type.site_reading_type_id"))
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the reading was created
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
