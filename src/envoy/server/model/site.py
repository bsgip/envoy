from datetime import datetime

from sqlalchemy import VARCHAR, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model import Base


class Site(Base):
    __tablename__ = "site"

    site_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nmi: Mapped[str] = mapped_column(VARCHAR(length=11), nullable=True)
    aggregator_id: Mapped[int] = mapped_column(
        ForeignKey("aggregator.aggregator_id"), nullable=False
    )
    # dnsp_id = mapped_column(ForeignKey("dnsp.dnsp_id"), nullable=False) # TODO

    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lfdi: Mapped[str] = mapped_column(VARCHAR(length=42), nullable=False, unique=True)
    sfdi: Mapped[int] = mapped_column(BigInteger, nullable=False)
    device_category: Mapped[str] = mapped_column(VARCHAR(length=8))
    # post_rate: Mapped[Integer] # TODO: should this live in notification/subscription tables?

    UniqueConstraint("sfdi", "aggregator_id", name="sfdi_aggregator_id_uc")