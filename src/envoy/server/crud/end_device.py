from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site import Site


async def select_aggregator_site_count(session: AsyncSession, aggregator_id: int):
    stmt = select(func.count()).select_from(
        select(Site.site_id).where(Site.aggregator_id == aggregator_id)
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_sites_with_aggregator_id(
    session: AsyncSession,
    aggregator_id: int,
    start: int,
    after: datetime,
    limit: int,
) -> list[Site]:
    stmt = (
        select(
            Site.site_id, Site.lfdi, Site.sfdi, Site.changed_time, Site.device_category
        )
        .where((Site.aggregator_id == aggregator_id) & (Site.changed_time >= after))
        .offset(start)
        .limit(limit)
        .order_by(
            Site.changed_time.desc(),
            Site.sfdi.asc(),
        )
    )

    resp = await session.execute(stmt)

    return resp.all()


async def select_single_site_with_site_id(
    session: AsyncSession, site_id: int, aggregator_id: int
) -> Optional[Site]:
    """Site and aggregator id need to be used to make sure the aggregator owns this site."""
    stmt = select(Site).where(
        (Site.aggregator_id == aggregator_id) & (Site.site_id == site_id)
    )

    resp = await session.execute(stmt)

    return resp.scalar_one()


async def upsert_site_for_aggregator(session: AsyncSession, site: Site) -> int:
    """Relying on postgresql dialect for upsert capability. Unfortunately this breaks the typical ORM insert pattern."""

    all_cols = dict(
        changed_time=site.changed_time,
        lfdi=site.lfdi,
        sfdi=site.sfdi,
        device_category=site.device_category,
        aggregator_id=site.aggregator_id,
    )
    update_cols = dict(
        changed_time=site.changed_time,
        device_category=site.device_category,
    )

    stmt = psql_insert(Site).values([all_cols])
    stmt = stmt.on_conflict_do_update(
        index_elements=[Site.aggregator_id, Site.sfdi],
        set_=update_cols,
    ).returning(Site.site_id)

    resp = await session.execute(stmt)
    return resp.scalar_one()
