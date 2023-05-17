from typing import Iterable

from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site_reading import SiteReading, SiteReadingType


async def upsert_site_reading_type_for_aggregator(
    session: AsyncSession, aggregator_id: int, site_reading_type: SiteReadingType
) -> int:
    """Creates or updates the specified site reading type. If site's aggregator_id doesn't match aggregator_id then
    this will raise an error without modifying the DB. Returns the site_reading_type_id of the inserted/existing site

    Relying on postgresql dialect for upsert capability. Unfortunately this breaks the typical ORM insert pattern.

    Returns the site_reading_type_id of the created/updated SiteReadingType"""

    if aggregator_id != site_reading_type.aggregator_id:
        raise ValueError(
            f"Specified aggregator_id {aggregator_id} mismatches site.aggregator_id {site_reading_type.aggregator_id}"
        )

    table = SiteReadingType.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns)]  # type: ignore [attr-defined]
    stmt = psql_insert(SiteReadingType).values(**{k: getattr(site_reading_type, k) for k in update_cols})
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            SiteReadingType.aggregator_id,
            SiteReadingType.site_id,
            SiteReadingType.uom,
            SiteReadingType.data_qualifier,
            SiteReadingType.flow_direction,
            SiteReadingType.accumulation_behaviour,
            SiteReadingType.kind,
            SiteReadingType.phase,
            SiteReadingType.power_of_ten_multiplier,
            SiteReadingType.default_interval_seconds,
        ],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    ).returning(SiteReadingType.site_reading_type_id)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def upsert_site_readings(session: AsyncSession, site_readings: Iterable[SiteReading]):
    """Creates or updates the specified site readings. It's assumed that each SiteReading will have
    been assigned a valid site_reading_type_id before calling this function. No validation will be made for ownership

    Relying on postgresql dialect for upsert capability. Unfortunately this breaks the typical ORM insert pattern."""

    table = SiteReading.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns)]  # type: ignore [attr-defined]
    stmt = psql_insert(SiteReadingType).values([{k: getattr(sr, k) for k in update_cols} for sr in site_readings])
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            SiteReading.site_reading_type_id,
            SiteReading.time_period_start,
        ],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    )

    await session.execute(stmt)
