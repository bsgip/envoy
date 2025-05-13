from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, BigInteger, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model.base import Base
from envoy.server.model.site import Site

DOE_DECIMAL_PLACES = 2
DOE_DECIMAL_POWER = pow(10, DOE_DECIMAL_PLACES)


class DynamicOperatingEnvelope(Base):
    """Represents a dynamic operating envelope for a site at a particular time interval"""

    __tablename__ = "dynamic_operating_envelope"
    dynamic_operating_envelope_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id"))  # The site that this doe applies to
    calculation_log_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id"), nullable=True, index=True
    )  # The calculation log that resulted in this DOE or None if there is no such link

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the doe was created
    changed_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # When the doe was created/changed
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Time that the doe comes into effect
    duration_seconds: Mapped[int] = mapped_column()  # number of seconds that this doe applies for
    import_limit_active_watts: Mapped[Decimal] = mapped_column(
        DECIMAL(16, DOE_DECIMAL_PLACES)
    )  # Constraint on imported active power
    export_limit_watts: Mapped[Decimal] = mapped_column(
        DECIMAL(16, DOE_DECIMAL_PLACES)
    )  # Constraint on exported active/reactive power

    site: Mapped["Site"] = relationship(lazy="raise")

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )  # This is to support finding DOE's that are either currently active or yet to start (i.e. not expired)
    # Ideally this would be Generated/Computed column but in order do this, we'd need support for the immutable
    # postgres function date_add(start_time, duration_seconds * interval '1 sec', 'UTC'). Unfortunately this was only
    # added in postgres 16 so we'd be cutting off large chunks of postgresql servers - instead we just manually populate
    # this as we go.

    __table_args__ = (
        UniqueConstraint("start_time", "site_id", name="start_time_site_id_uc"),
        Index("ix_dynamic_operating_envelope_end_time_site_id", "end_time", "site_id"),
    )
