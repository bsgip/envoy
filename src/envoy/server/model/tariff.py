from datetime import datetime
from decimal import Decimal
from typing import Optional

from envoy_schema.server.schema.sep2.types import CurrencyCode
from sqlalchemy import DECIMAL, BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base
from envoy.server.model.site import Site

PRICE_DECIMAL_PLACES = 4  # How many decimal places do we store / distribute prices with?
PRICE_DECIMAL_POWER = pow(10, PRICE_DECIMAL_PLACES)


class Tariff(Base):
    """Represents a top level Tariff that will capture all details about the tariff, when it applies and who
    it will apply to"""

    __tablename__ = "tariff"
    tariff_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))  # descriptive name of the tariff
    dnsp_code: Mapped[str] = mapped_column(String(20))  # code assigned by the DNSP for their own internal processes
    currency_code: Mapped[CurrencyCode] = mapped_column(Integer)  # ISO 4217 numerical currency code - eg AUD = 36
    fsa_id: Mapped[int] = mapped_column(
        Integer, index=True, server_default="1"
    )  # Function set assignment ID that will group this Tariff with other Tariffs
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the tariff was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the tariff was created/changed

    generated_rates: Mapped[list["TariffGeneratedRate"]] = relationship(back_populates="tariff", lazy="raise")


class TariffGeneratedRate(Base):
    """Represents a generated tariff rate for a specific time interval/site. These will take precedence over
    the 'default' rate for a particular time slice"""

    __tablename__ = "tariff_generated_rate"
    tariff_generated_rate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariff.tariff_id"))  # The tariff
    site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id"))  # The site that this rate applies to

    calculation_log_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id"), nullable=True, index=True
    )  # The calculation log that resulted in this rate or None if there is no such link

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the rate was created
    changed_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # When the rate was created/changed
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Time that the tariff comes into effect
    duration_seconds: Mapped[int] = mapped_column()  # number of seconds that this rate applies for
    import_active_price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, PRICE_DECIMAL_PLACES)
    )  # calculated rate for importing active power - price is dollars per kw/h
    export_active_price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, PRICE_DECIMAL_PLACES)
    )  # calculated rate for exporting active power - price is dollars per kw/h
    import_reactive_price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, PRICE_DECIMAL_PLACES)
    )  # calculated rate for importing reactive power - price is dollars per kvar/h
    export_reactive_price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, PRICE_DECIMAL_PLACES)
    )  # calculated rate for exporting reactive power - price is dollars per kvar/h

    tariff: Mapped["Tariff"] = relationship(back_populates="generated_rates", lazy="raise")
    site: Mapped["Site"] = relationship(lazy="raise")

    __table_args__ = (UniqueConstraint("tariff_id", "site_id", "start_time", name="tariff_id_site_id_start_time_uc"),)
