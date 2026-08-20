from datetime import datetime

from sqlalchemy import BOOLEAN, INTEGER, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX, ArchiveBase
from envoy.server.model.server import RuntimeServerConfig


class ArchiveRuntimeServerConfig(ArchiveBase):
    """Represents a historical snapshot of the (single row) RuntimeServerConfig table"""

    __tablename__ = ARCHIVE_TABLE_PREFIX + RuntimeServerConfig.__tablename__

    runtime_server_config_id: Mapped[int] = mapped_column(INTEGER, index=True)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    dcap_pollrate_seconds: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    edevl_pollrate_seconds: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    fsal_pollrate_seconds: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    derpl_pollrate_seconds: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    derl_pollrate_seconds: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    mup_postrate_seconds: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    site_control_pow10_encoding: Mapped[int | None] = mapped_column(INTEGER, nullable=True)

    disable_edev_registration: Mapped[bool | None] = mapped_column(BOOLEAN, nullable=True)
