from datetime import datetime
from typing import cast

from sqlalchemy import ColumnElement, CursorResult, delete
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import delete_rows_into_archive
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.base import Base
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate


async def _delete_matching(
    session: AsyncSession,
    source_table: type[Base],
    archive_table: type[ArchiveBase],
    where_clause: ColumnElement[bool],
    archive: bool,
    deleted_time: datetime,
) -> int:
    """Deletes all source_table rows matching where_clause. If archive is True, the rows will first be copied into
    archive_table (with deleted_time). Returns the number of deleted rows."""
    if archive:
        return await delete_rows_into_archive(
            session, source_table, archive_table, deleted_time, lambda q: q.where(where_clause)
        )

    result = await session.execute(delete(source_table).where(where_clause))
    return cast(CursorResult, result).rowcount


async def delete_expired_site_controls(
    session: AsyncSession, expired_before: datetime, archive: bool, deleted_time: datetime
) -> int:
    """Deletes ALL site controls (DynamicOperatingEnvelope) whose end_time is <= expired_before (across all
    SiteControlGroups). Returns the number of deleted controls.

    expired_before: Controls with an end_time at or before this value will be removed
    archive: If True - deleted controls will be copied to the archive table (with deleted_time). Otherwise they are
             permanently deleted
    deleted_time: The deleted_time to apply to archived records (ignored if archive is False)"""
    return await _delete_matching(
        session,
        DynamicOperatingEnvelope,
        ArchiveDynamicOperatingEnvelope,
        DynamicOperatingEnvelope.end_time <= expired_before,
        archive,
        deleted_time,
    )


async def delete_expired_tariff_generated_rates(
    session: AsyncSession, expired_before: datetime, archive: bool, deleted_time: datetime
) -> int:
    """Deletes ALL TariffGeneratedRates whose end_time is <= expired_before (across all tariffs). Returns the number of
    deleted rates.

    expired_before: Rates with an end time at or before this value will be removed
    archive: If True - deleted rates will be copied to the archive table (with deleted_time). Otherwise they are
             permanently deleted
    deleted_time: The deleted_time to apply to archived records (ignored if archive is False)"""
    return await _delete_matching(
        session,
        TariffGeneratedRate,
        ArchiveTariffGeneratedRate,
        TariffGeneratedRate.end_time <= expired_before,
        archive,
        deleted_time,
    )


async def delete_archive_records(
    session: AsyncSession, archive_table: type[ArchiveBase], archived_before: datetime
) -> int:
    """Permanently deletes all records from archive_table whose archive_time is <= archived_before. Returns the number
    of deleted records."""
    result = await session.execute(delete(archive_table).where(archive_table.archive_time <= archived_before))
    return cast(CursorResult, result).rowcount
