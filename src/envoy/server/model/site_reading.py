from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model import Base


class SiteReadingSet(Base):
    __tablename__ = "site_reading_set"

    site_reading_set_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.site_id"))  # The site this reading applies to
    aggregator_id: Mapped[int] = mapped_column(
        ForeignKey("aggregator.aggregator_id")
    )  # Tracks aggregator at time of write


class SiteReading(Base):
    __tablename__ = "site_reading"

    site_reading_id: Mapped[int] = mapped_column(primary=True, autoincrement=True)
    site_reading_set_id: Mapped[int] = mapped_column(ForeignKey("site_read_set.site_reading_set_id"))
