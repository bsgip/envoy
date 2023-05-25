from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site import Site


async def select_aggregator_site_count(session: AsyncSession, aggregator_id: int, after: datetime) -> int:
    """Fetches the number of sites 'owned' by the specified aggregator (with an additional filter on the site
    changed_time)

    after: Only sites with a changed_time greater than this value will be counted (set to 0 to count everything)"""
    # fmt: off
    stmt = (
        select(func.count())
        .select_from(Site)
        .where((Site.aggregator_id == aggregator_id) & (Site.changed_time >= after))
    )
    # fmt: on
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_sites_with_aggregator_id(
    session: AsyncSession,
    aggregator_id: int,
    start: int,
    after: datetime,
    limit: int,
) -> Sequence[Site]:
    """Selects sites for an aggregator with some basic pagination / filtering based on change time

    Results will be ordered according to sep2 spec which is changedTime then sfdi"""
    stmt = (
        select(Site)
        .where((Site.aggregator_id == aggregator_id) & (Site.changed_time >= after))
        .offset(start)
        .limit(limit)
        .order_by(
            Site.changed_time.desc(),
            Site.sfdi.asc(),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def select_single_site_with_site_id(session: AsyncSession, site_id: int, aggregator_id: int) -> Optional[Site]:
    """Site and aggregator id need to be used to make sure the aggregator owns this site."""
    stmt = select(Site).where((Site.aggregator_id == aggregator_id) & (Site.site_id == site_id))
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_single_site_with_lfdi(session: AsyncSession, lfdi: str, aggregator_id: int) -> Optional[Site]:
    """Site and aggregator id need to be used to make sure the aggregator owns this site."""
    stmt = select(Site).where((Site.aggregator_id == aggregator_id) & (Site.lfdi == lfdi))
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def upsert_site_for_aggregator(session: AsyncSession, aggregator_id: int, site: Site) -> int:
    """Inserts or updates the specified site. If site's aggregator_id doesn't match aggregator_id then this will
    raise an error without modifying the DB. Returns the site_id of the inserted/updated site

    Inserts/Updates will be based on matches on the agg_id / sfdi index. Attempts to mutate agg_id/sfdi will result
    in inserting a new record.

    Relying on postgresql dialect for upsert capability. Unfortunately this breaks the typical ORM insert pattern."""

    if aggregator_id != site.aggregator_id:
        raise ValueError(f"Specified aggregator_id {aggregator_id} mismatches site.aggregator_id {site.aggregator_id}")

    table = Site.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns)]  # type: ignore [attr-defined]
    stmt = psql_insert(Site).values(**{k: getattr(site, k) for k in update_cols})
    stmt = stmt.on_conflict_do_update(
        index_elements=[Site.aggregator_id, Site.sfdi],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    ).returning(Site.site_id)

    resp = await session.execute(stmt)
    return resp.scalar_one()
