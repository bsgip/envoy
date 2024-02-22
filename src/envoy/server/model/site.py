from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.types import DeviceCategory
from sqlalchemy import INTEGER, VARCHAR, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base


class Site(Base):
    __tablename__ = "site"

    site_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nmi: Mapped[Optional[str]] = mapped_column(VARCHAR(length=11), nullable=True)
    aggregator_id: Mapped[int] = mapped_column(ForeignKey("aggregator.aggregator_id"), nullable=False)

    timezone_id: Mapped[str] = mapped_column(VARCHAR(length=64), nullable=False)  # tz_id name of the local timezone
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lfdi: Mapped[str] = mapped_column(VARCHAR(length=42), nullable=False, unique=True)
    sfdi: Mapped[int] = mapped_column(BigInteger, nullable=False)
    device_category: Mapped[DeviceCategory] = mapped_column(INTEGER, nullable=False)

    assignments: Mapped[list["SiteGroupAssignment"]] = relationship(
        back_populates="site",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # What assignments reference this group

    __table_args__ = (
        UniqueConstraint("sfdi", "aggregator_id", name="sfdi_aggregator_id_uc"),
        UniqueConstraint("lfdi", "aggregator_id", name="lfdi_aggregator_id_uc"),  # Mirror Metering requires unique lfdi
    )


class SiteGroup(Base):
    """Site groups are a way of logically grouping Sites independent of their aggregator/other details. Each Site may
    belong to multiple groups and its expected that these groupings are managed via the admin server"""

    __tablename__ = "site_group"

    site_group_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(VARCHAR(length=128))  # Name/Title of this group - must be unique
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    assignments: Mapped[list["SiteGroupAssignment"]] = relationship(
        back_populates="group",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # What assignments reference this group

    __table_args__ = (UniqueConstraint("name", name="name_uc"),)


class SiteGroupAssignment(Base):
    """Provides a many-many mapping between Site and SiteGroup"""

    __tablename__ = "site_group_assignment"

    site_group_assignment_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id", ondelete="CASCADE"))
    site_group_id: Mapped[int] = mapped_column(ForeignKey("site_group.site_group_id", ondelete="CASCADE"))

    site: Mapped["Site"] = relationship(back_populates="assignments", lazy="raise")
    group: Mapped["SiteGroup"] = relationship(back_populates="assignments", lazy="raise")

    # We don't want a single site to be linked to a group multiple times
    __table_args__ = (UniqueConstraint("site_id", "site_group_id", name="site_id_site_group_id_uc"),)
