from datetime import datetime
from typing import Optional

from sqlalchemy import INTEGER, VARCHAR, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model import Base
from envoy.server.schema.sep2.types import DeviceCategory


class Site(Base):
    __tablename__ = "site"

    site_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nmi: Mapped[Optional[str]] = mapped_column(VARCHAR(length=11), nullable=True)
    aggregator_id: Mapped[int] = mapped_column(ForeignKey("aggregator.aggregator_id"), nullable=False)

    timezone_id: Mapped[str] = mapped_column(VARCHAR(length=64), nullable=False)  # tz_id name of the local timezone
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lfdi: Mapped[str] = mapped_column(VARCHAR(length=42), nullable=False, unique=True)
    sfdi: Mapped[int] = mapped_column(BigInteger, nullable=False)
    device_category: Mapped[DeviceCategory] = mapped_column(INTEGER, nullable=False)

    __table_args__ = (
        UniqueConstraint("sfdi", "aggregator_id", name="sfdi_aggregator_id_uc"),
        UniqueConstraint("lfdi", "aggregator_id", name="lfdi_aggregator_id_uc"),  # Mirror Metering requires unique lfdi
    )


# class SiteGroup(Base):
#     """A way of logically grouping a site for a particular purpose"""

#     __tablename__ = "site_group"

#     site_group_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     name: Mapped[str] = mapped_column(VARCHAR(length=64), nullable=True)  # Human readable name of the group


# class SiteGroupAssignment(Base):
#     """Links a site to a group such that there can be a many-many relationship between the two"""

#     __tablename__ = "site_group_assignment"

#     site_group_assignment_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     site_group_id: Mapped[int] = mapped_column(ForeignKey("site_group.site_group_id"), nullable=False)
#     site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id"), nullable=False)

#     __table_args__ = (UniqueConstraint("site_group_id", "site_id", name="site_group_id_site_id_uc"),)
