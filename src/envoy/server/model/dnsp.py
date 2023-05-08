from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model import Base


class DNSP(Base):
    """Represents a Distribution Network Service Provider which is a top level entity that can access the majority
    of entities "underneath" it"""

    __tablename__ = "dnsp"

    dnsp_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
