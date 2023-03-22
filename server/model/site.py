from sqlalchemy import VARCHAR, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.model import Base


class Site(Base):
    __tablename__ = "site"

    site_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nmi = mapped_column(VARCHAR(length=11), nullable=True)
    aggregator_id = mapped_column(
        ForeignKey("aggregator.aggregator_id"), nullable=False
    )
    # dnsp_id = mapped_column(ForeignKey("dnsp.dnsp_id"), nullable=False) # TODO

    changed_time = mapped_column(DateTime(timezone=True))
    lfdi = mapped_column(VARCHAR(length=42), nullable=False, unique=True)
    sfdi = mapped_column(Integer, nullable=False)
    device_category = mapped_column(VARCHAR(length=8))
    # post_rate: Mapped[Integer] # TODO: should this live in notification/subscription tables?

    UniqueConstraint("sfdi", "aggregator_id", name="sfdi_aggregator_id_uc")
