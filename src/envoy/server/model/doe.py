from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model.base import Base
from envoy.server.model.site import Site

DOE_DECIMAL_PLACES = 2
DOE_DECIMAL_POWER = pow(10, DOE_DECIMAL_PLACES)


class DynamicOperatingEnvelope(Base):
    """Represents a dynamic operating envelope for a site at a particular time interval"""

    __tablename__ = "dynamic_operating_envelope"
    dynamic_operating_envelope_id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id"))  # The site that this doe applies to

    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the doe was created/changed
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Time that the doe comes into effect
    duration_seconds: Mapped[int] = mapped_column()  # number of seconds that this doe applies for
    import_limit_active_watts: Mapped[Decimal] = mapped_column(DECIMAL(16, DOE_DECIMAL_PLACES))  # Constraint on imported active power  # noqa e501
    export_limit_watts: Mapped[Decimal] = mapped_column(DECIMAL(16, DOE_DECIMAL_PLACES))  # Constraint on exported active/reactive power # noqa e501

    site: Mapped["Site"] = relationship(lazy="raise")

    __table_args__ = (
        UniqueConstraint("site_id", "start_time", name="site_id_start_time_uc"),
    )
