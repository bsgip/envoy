from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from server.model import Base


class Aggregator(Base):
    "Represents a Distributed Energy Resource (DER) aggregator"
    __tablename__ = "aggregator"

    aggregator_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]


class AggregatorCertificateAssignment(Base):
    """Links a specific Certificate to an Aggregator allowing a many-many relationship"""

    __tablename__ = "aggregator_certificate_assignment"
    assignment_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    certificate_id = mapped_column(
        ForeignKey("certificate.certificate_id"), nullable=False
    )
    aggregator_id = mapped_column(
        ForeignKey("aggregator.aggregator_id"), nullable=False
    )
