from datetime import datetime

from sqlalchemy import VARCHAR, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base


class Aggregator(Base):
    "Represents a Distributed Energy Resource (DER) aggregator"
    __tablename__ = "aggregator"

    aggregator_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]

    domains: Mapped[list["AggregatorDomain"]] = relationship(
        back_populates="aggregator",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # The set of domains that this Aggregator has registered


class AggregatorCertificateAssignment(Base):
    """Links a specific Certificate to an Aggregator allowing a many-many relationship"""

    __tablename__ = "aggregator_certificate_assignment"
    assignment_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("certificate.certificate_id"), nullable=False)
    aggregator_id: Mapped[int] = mapped_column(ForeignKey("aggregator.aggregator_id"), nullable=False)


class AggregatorDomain(Base):
    """Represents a whitelisted domain name controlled by Aggregator"""

    __tablename__ = "aggregator_domain"

    aggregator_domain_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aggregator_id: Mapped[int] = mapped_column(ForeignKey("aggregator.aggregator_id", ondelete="CASCADE"))

    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the domain was created/changed
    domain: Mapped[str] = mapped_column(VARCHAR(length=512), nullable=False)  # The whitelisted FQ domain name

    aggregator: Mapped["Aggregator"] = relationship(back_populates="domains", lazy="raise")
