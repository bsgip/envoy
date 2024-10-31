from datetime import datetime
from decimal import Decimal
from typing import Optional

from envoy_schema.server.schema.sep2.types import CurrencyCode
from sqlalchemy import DECIMAL, INTEGER, BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

import envoy.server.model as original_models
from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX, ArchiveBase


class ArchiveTariff(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.Tariff.__tablename__  # type: ignore
    tariff_id: Mapped[int] = mapped_column(INTEGER, index=True)
    name: Mapped[str] = mapped_column(String(64))
    dnsp_code: Mapped[str] = mapped_column(String(20))
    currency_code: Mapped[CurrencyCode] = mapped_column(Integer)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArchiveTariffGeneratedRate(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.TariffGeneratedRate.__tablename__  # type: ignore
    tariff_generated_rate_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tariff_id: Mapped[int] = mapped_column(INTEGER)
    site_id: Mapped[int] = mapped_column(INTEGER)
    calculation_log_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column(INTEGER)
    import_active_price: Mapped[Decimal] = mapped_column(DECIMAL(10, original_models.tariff.PRICE_DECIMAL_PLACES))
    export_active_price: Mapped[Decimal] = mapped_column(DECIMAL(10, original_models.tariff.PRICE_DECIMAL_PLACES))
    import_reactive_price: Mapped[Decimal] = mapped_column(DECIMAL(10, original_models.tariff.PRICE_DECIMAL_PLACES))
    export_reactive_price: Mapped[Decimal] = mapped_column(DECIMAL(10, original_models.tariff.PRICE_DECIMAL_PLACES))
