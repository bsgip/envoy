from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, VARCHAR, BigInteger, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model.base import Base
from envoy.server.model.constants import DOE_DECIMAL_PLACES
from envoy.server.model.site import Site


class SiteControlGroup(Base):
    """Represents a top level grouping of controls. The grouping is NOT site scoped but the underlying controls will be

    A group contains metadata and a "primacy" to distinguish it's controls from other SiteControlGroups"""

    __tablename__ = "site_control_group"
    site_control_group_id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(VARCHAR(length=32))  # Human readable description of this group
    primacy: Mapped[int] = (
        mapped_column()
    )  # The priority level of this group's controls relative to other groups. Lower is higher priority.
    fsa_id: Mapped[int] = mapped_column(
        index=True, server_default="1"
    )  # The function set assignment ID that "groups" this SiteControlGroup with other SiteControlGroups

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # When the group was created
    changed_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # When the group was created/changed

    dynamic_operating_envelopes: Mapped[list["DynamicOperatingEnvelope"]] = relationship(
        lazy="raise", back_populates="site_control_group"
    )

    Index(
        "ix_site_control_group_primacy_site_control_group_id",
        "primacy",
        "site_control_group_id",
    ),


# TODO: Rename this and related archive to SiteControl. These entities will eventually hold more than
# just DOE related information, e.g. set-point control, etc.
class DynamicOperatingEnvelope(Base):
    """Represents a dynamic operating envelope for a site at a particular time interval"""

    __tablename__ = "dynamic_operating_envelope"
    dynamic_operating_envelope_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_control_group_id: Mapped[int] = mapped_column(
        ForeignKey("site_control_group.site_control_group_id")
    )  # The group that this doe belongs to
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
    randomize_start_seconds: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # Client directive to randomize the actual start_time by this many seconds
    import_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, DOE_DECIMAL_PLACES), nullable=True
    )  # Constraint on imported active power
    export_limit_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, DOE_DECIMAL_PLACES), nullable=True
    )  # Constraint on exported active power TODO: rename to ..active_watts

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )  # This is to support finding DOE's that are either currently active or yet to start (i.e. not expired)
    # Ideally this would be Generated/Computed column but in order do this, we'd need support for the immutable
    # postgres function date_add(start_time, duration_seconds * interval '1 sec', 'UTC'). Unfortunately this was only
    # added in postgres 16 so we'd be cutting off large chunks of postgresql servers - instead we just manually populate
    # this as we go.

    # NOTE: We've decided to include these 'non-DOE' related fields (that map to DERControl elements) here and
    # eventually generalise this to capture specifically the DERControl that are of interest to CSIP-AUS (i.e. not
    # necessarily everything in core IEEE2030.5).
    generation_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(16, DOE_DECIMAL_PLACES), nullable=True
    )
    load_limit_active_watts: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(16, DOE_DECIMAL_PLACES), nullable=True)
    set_energized: Mapped[Optional[bool]] = mapped_column(nullable=True)
    set_connected: Mapped[Optional[bool]] = mapped_column(nullable=True)

    site: Mapped["Site"] = relationship(lazy="raise")

    site_control_group: Mapped["SiteControlGroup"] = relationship(
        back_populates="dynamic_operating_envelopes", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint(
            "site_control_group_id", "start_time", "site_id", name="site_control_group_id_start_time_site_id_uc"
        ),
        Index(
            "ix_site_control_group_dynamic_operating_envelope_end_time_site",
            "site_control_group_id",
            "end_time",
            "site_id",
        ),
    )
