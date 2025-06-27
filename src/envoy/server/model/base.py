from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Certificate(Base):
    """Reference store for issued TLS certificates"""

    __tablename__ = "certificate"

    certificate_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    lfdi: Mapped[str] = mapped_column(sa.VARCHAR(length=42), nullable=False, unique=True)
    expiry: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
