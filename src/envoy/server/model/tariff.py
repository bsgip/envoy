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
from sqlalchemy import INTEGER, VARCHAR, BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base
from envoy.server.model.site import Site


class Tariff(Base):
    """Represents a top level Tariff that will capture all details about the tariff, when it applies and who
    it will apply to"""

    __tablename__ = "tariff"
    tariff_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))  # descriptive name of the tariff
    dnsp_code: Mapped[str] = mapped_column(String(20))  # code assigned by the DNSP for their own internal processes
    currency_code: Mapped[CurrencyCode] = mapped_column(Integer)  # ISO 4217 numerical currency code - eg AUD = 36
    price_power_of_ten_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    primacy: Mapped[int] = mapped_column(INTEGER)

    fsa_id: Mapped[int] = mapped_column(
        Integer, index=True, server_default="1"
    )  # Function set assignment ID that will group this Tariff with other Tariffs

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the tariff was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the tariff was created/changed

    tariff_components: Mapped[list["TariffComponent"]] = relationship(back_populates="tariff", lazy="raise")


class TariffComponent(Base):
    """Represents a single pricing "unit of measure". All TariffGeneratedRate instances underneath it will dictate
    individual prices but this entity will describe what is actually being priced"""

    __tablename__ = "tariff_component"
    tariff_component_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariff.tariff_id"))  # The tariff that owns this component

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

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the reading set was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)  # When the rec was last altered

    tariff: Mapped["Tariff"] = relationship(back_populates="tariff_components", lazy="raise")
    tariff_generated_rates: Mapped[list["TariffGeneratedRate"]] = relationship(
        back_populates="tariff_component", lazy="raise"
    )

    __table_args__ = (
        Index(
            "ix_tariff_component_tariff_id",
            "tariff_id",
        ),
    )


class TariffGeneratedRate(Base):
    """Represents a generated tariff rate for a specific time interval/site."""

    __tablename__ = "tariff_generated_rate"
    tariff_generated_rate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariff.tariff_id"))  # The tariff that owns the parent component
    tariff_component_id: Mapped[int] = mapped_column(
        ForeignKey("tariff_component.tariff_component_id")
    )  # The parent component that describes uom being priced
    site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id"))  # The site that this rate applies to

    calculation_log_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id"), nullable=True, index=True
    )  # The calculation log that resulted in this rate or None if there is no such link

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Time that the tariff comes into effect
    duration_seconds: Mapped[int] = mapped_column()  # number of seconds that this rate applies for
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )  # This is to support finding DOE's that are either currently active or yet to start (i.e. not expired)
    # Ideally this would be Generated/Computed column but in order do this, we'd need support for the immutable
    # postgres function date_add(start_time, duration_seconds * interval '1 sec', 'UTC'). Unfortunately this was only
    # added in postgres 16 so we'd be cutting off large chunks of postgresql servers - instead we just manually populate
    # this as we go.

    price_pow10_encoded: Mapped[int] = mapped_column(
        INTEGER
    )  # The actual price - pow10 encoded via 10 ^ Tariff.price_power_of_ten_multiplier * price_pow10_encoded
    # eg: if price_pow10_encoded = 1234 and Tariff.price_power_of_ten_multiplier is -2 then the actual price is $12.34

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the rate was created
    changed_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # When the rate was created/changed

    tariff_component: Mapped["TariffComponent"] = relationship(back_populates="tariff_generated_rates", lazy="raise")
    site: Mapped["Site"] = relationship(lazy="raise")

    __table_args__ = (
        Index(
            "ix_tariff_generated_rate_tariff_component_id_end_time_site_id",
            "tariff_component_id",
            "end_time",
            "site_id",
        ),  # Used by the primary csip-aus DERControl list endpoint (for fetching via RateComponents)
        Index(
            "ix_tariff_generated_rate_tariff_id_end_time_site_id",
            "tariff_id",
            "end_time",
            "site_id",
        ),  # Used by the primary csip-aus DERControl list endpoint (for fetching via Tariff)
    )
