from base import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class User(Base):
    """Represents a single user login to the server. Doesn't grant any specific access permissions until
    linked to a DNSP/Aggregator etc"""

    __tablename__ = "user"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(128))
    short_name: Mapped[str] = mapped_column(String(32))
    full_name: Mapped[str] = mapped_column(String(64))
