from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import DateTime, VARCHAR

from sqlalchemy import MetaData

metadata = MetaData()

Base = declarative_base(metadata=metadata)


class Certificate(Base):
    """Reference store for issued TLS certificates"""

    __tablename__ = "certificate"

    certificate_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created = mapped_column(DateTime(timezone=True))
    lfdi = mapped_column(VARCHAR(length=42), nullable=False)
    expiry = mapped_column(DateTime(timezone=True), nullable=False)
