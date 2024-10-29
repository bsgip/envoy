from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from envoy.server.model.base import Base

# All of our archive table names will have this prefix
ARCHIVE_TABLE_PREFIX = "archive_"

# All of our archive classes/types will have this prefix
ARCHIVE_TYPE_PREFIX = "Archive"


class ArchiveBase(Base):
    """An archive table is a (mostly non indexed) copy of historical rows from certain key tables. Each row will
    represent a moment in time snapshot of a single row from that table. That original row might have multiple
    archived copies, each showing historical values at the moment they updated.

    Archive tables will maintain the same column structure as the table they are archiving but will also keep track
    of when each snapshot was made and whether the original record has been deleted or not

    ForeignKeys are NOT maintained in archive tables. Neither are relationships or anything else requiring a join"""

    __abstract__ = True

    # The PK for uniquely identifying any archived row
    archive_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # When the archived row was copied into the archived table
    # This is NOT guaranteed to align with the changed_time (for notification server lookups)
    # it's purely an auditing value for when the row archived
    archive_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # If set, this will be when the row in the original table was deleted (meaning this should be the archived row).
    # This WILL align with the changed_times shared with the notification server.
    deleted_time: Mapped[bool] = mapped_column(DateTime(timezone=True), server_default=None, nullable=True, index=True)


ARCHIVE_BASE_COLUMNS: set[str] = {"archive_id", "archive_time", "deleted_time"}
