from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.doe import DynamicOperatingEnvelope


async def upsert_many_doe(session: AsyncSession, doe_list: list[DynamicOperatingEnvelope]) -> None:
    """Adds a multiple DynamicOperatingEnvelope into the db. Returns None."""
    table = DynamicOperatingEnvelope.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    stmt = psql_insert(DynamicOperatingEnvelope).values([{k: getattr(doe, k) for k in update_cols} for doe in doe_list])
    stmt = stmt.on_conflict_do_update(
        index_elements=[DynamicOperatingEnvelope.site_id, DynamicOperatingEnvelope.start_time],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    )
    await session.execute(stmt)


async def count_all_does(session: AsyncSession, changed_after: Optional[datetime]) -> int:
    """Admin counting of does - no filtering on aggregator is made. If changed_after is specified, only
    does that have their changed_time >= changed_after will be included"""
    stmt = select(func.count()).select_from(DynamicOperatingEnvelope)

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(DynamicOperatingEnvelope.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_does(
    session: AsyncSession,
    start: int,
    limit: int,
    changed_after: Optional[datetime],
) -> Sequence[DynamicOperatingEnvelope]:
    """Admin selecting of does - no filtering on aggregator is made. Returns ordered by dynamic_operating_envelope_id

    changed_after is INCLUSIVE"""

    stmt = (
        select(DynamicOperatingEnvelope)
        .offset(start)
        .limit(limit)
        .order_by(
            DynamicOperatingEnvelope.dynamic_operating_envelope_id.asc(),
        )
    )

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(DynamicOperatingEnvelope.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalars().all()
