from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base
from envoy.server.schema.sep2.pricing import CurrencyCode


class Tariff(Base):
    """Represents a top level Tariff that will capture all details about the tariff, when it applies and who
    it will apply to"""

    __tablename__ = "tariff"
    tariff_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))  # descriptive name of the tariff
    dnsp_code: Mapped[str] = mapped_column(String(20))  # code assigned by the DNSP for their own internal processes
    currency_code: Mapped[CurrencyCode] = mapped_column(Integer)  # ISO 4217 numerical currency code - eg AUD = 36

    generated_rates: Mapped[list["TariffGeneratedRate"]] = relationship(back_populates="tariff")


class TariffGeneratedRate(Base):
    """Represents a generated tariff rate for a specific time interval/site. These will take precedence over
    the 'default' rate for a particular time slice"""

    __tablename__ = "tariff_generated_rate"
    tariff_generated_rate_id: Mapped[int] = mapped_column(primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariff.tariff_id"))  # The tariff
    site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id"))  # The site that this rate applies to

    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the rate was created/changed
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Time that the tariff comes into effect
    duration_seconds: Mapped[int] = mapped_column()  # number of seconds that this rate applies for

    tariff: Mapped["Tariff"] = relationship(back_populates="generated_rates")

    __table_args__ = (
        UniqueConstraint("tariff_id", "site_id", "start_time", name="tariff_id_site_id_start_time_uc"),
    )