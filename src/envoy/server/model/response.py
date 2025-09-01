from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.response import ResponseType
from sqlalchemy import INTEGER, SMALLINT, BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.mapper.constants import PricingReadingType
from envoy.server.model.base import Base
from envoy.server.model.site import Site


class DynamicOperatingEnvelopeResponse(Base):
    """Represents a client response to a specific dynamic operating envelope.

    These are explicitly NOT archived - primarily for performance / storage purposes"""

    __tablename__ = "dynamic_operating_envelope_response"
    dynamic_operating_envelope_response_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    dynamic_operating_envelope_id_snapshot: Mapped[int] = mapped_column(BigInteger)  # The doe this response applies to
    site_id: Mapped[int] = mapped_column(
        ForeignKey("site.site_id", ondelete="CASCADE")
    )  # The parent site that ultimately owns the DOE. Redundant, but included for select query performance

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the response was created

    response_type: Mapped[Optional[ResponseType]] = mapped_column(INTEGER, nullable=True)

    site: Mapped[Site] = relationship(lazy="raise")

    __table_args__ = (
        Index("ix_dynamic_operating_envelope_response_site_id_created_time", "site_id", "created_time", unique=False),
    )


class TariffGeneratedRateResponse(Base):
    """Represents a client response to a specific tariff generated rate

    These are explicitly NOT archived - primarily for performance / storage purposes"""

    __tablename__ = "tariff_generated_rate_response"
    tariff_generated_rate_response_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tariff_generated_rate_id_snapshot: Mapped[int] = mapped_column(BigInteger)  # The rate this response applies to
    site_id: Mapped[int] = mapped_column(
        ForeignKey("site.site_id", ondelete="CASCADE")
    )  # The parent site that ultimately owns the rate. Redundant, but included for select query performance

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the response was created

    response_type: Mapped[Optional[ResponseType]] = mapped_column(INTEGER, nullable=True)
    pricing_reading_type: Mapped[PricingReadingType] = mapped_column(
        SMALLINT
    )  # The specific price component being responded to (eg: is it for the active price in a TariffGeneratedRate)

    site: Mapped[Site] = relationship(lazy="raise")

    __table_args__ = (
        Index("ix_tariff_generated_rate_response_site_id_created_time", "site_id", "created_time", unique=False),
    )
