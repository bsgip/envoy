from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.types import (
    AccumulationBehaviourType,
    CommodityType,
    CurrencyCode,
    DataQualifierType,
    FlowDirectionType,
    KindType,
    PhaseCode,
    RoleFlagsType,
    UomType,
)
from sqlalchemy import INTEGER, VARCHAR, BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

import envoy.server.model as original_models
from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX, ArchiveBase


class ArchiveTariff(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.Tariff.__tablename__  # type: ignore
    tariff_id: Mapped[int] = mapped_column(INTEGER, index=True)
    name: Mapped[str] = mapped_column(String(64))
    dnsp_code: Mapped[str] = mapped_column(String(20))
    currency_code: Mapped[CurrencyCode] = mapped_column(Integer)
    price_power_of_ten_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    primacy: Mapped[int] = mapped_column(INTEGER)

    fsa_id: Mapped[int] = mapped_column(Integer)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArchiveTariffComponent(ArchiveBase):
    """Represents a single pricing "unit of measure". All TariffGeneratedRate instances underneath it will dictate
    individual prices but this entity will describe what is actually being priced"""

    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.TariffComponent.__tablename__
    tariff_component_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tariff_id: Mapped[int] = mapped_column(INTEGER)

    description: Mapped[Optional[str]] = mapped_column(VARCHAR(length=32), nullable=True)
    version: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    role_flags: Mapped[RoleFlagsType] = mapped_column(INTEGER)

    # ReadingType fields
    accumulation_behaviour: Mapped[Optional[AccumulationBehaviourType]] = mapped_column(INTEGER, nullable=True)
    commodity: Mapped[Optional[CommodityType]] = mapped_column(INTEGER, nullable=True)
    data_qualifier: Mapped[Optional[DataQualifierType]] = mapped_column(INTEGER, nullable=True)
    flow_direction: Mapped[Optional[FlowDirectionType]] = mapped_column(INTEGER, nullable=True)
    kind: Mapped[Optional[KindType]] = mapped_column(INTEGER, nullable=True)
    phase: Mapped[Optional[PhaseCode]] = mapped_column(INTEGER, nullable=True)
    power_of_ten_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    uom: Mapped[Optional[UomType]] = mapped_column(INTEGER, nullable=True)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the reading set was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the rec was last altered


class ArchiveTariffGeneratedRate(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.TariffGeneratedRate.__tablename__  # type: ignore
    tariff_generated_rate_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tariff_component_id: Mapped[int] = mapped_column(INTEGER)
    tariff_id: Mapped[int] = mapped_column(INTEGER)
    site_id: Mapped[int] = mapped_column(INTEGER)
    calculation_log_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column(INTEGER)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    price_pow10_encoded: Mapped[int] = mapped_column(INTEGER)

    __table_args__ = (
        Index(
            "archive_tariff_generated_rate_tariff_id_end_time_deleted_time_site_id",
            "tariff_id",
            "end_time",
            "deleted_time",
            "site_id",
        ),  # This is to support finding rates that have been deleted (or cancelled)
        Index(
            "archive_tariff_generated_rate_tariff_component_id_end_time_deleted_time_site_id",
            "tariff_component_id",
            "end_time",
            "deleted_time",
            "site_id",
        ),  # This is to support finding rates that have been deleted (or cancelled)
    )
