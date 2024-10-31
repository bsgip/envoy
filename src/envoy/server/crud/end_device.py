from datetime import datetime
from typing import Optional, Sequence

from envoy_schema.server.schema.sep2.types import DeviceCategory
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud import common
from envoy.server.crud.aggregator import select_aggregator
from envoy.server.crud.archive import copy_rows_into_archive
from envoy.server.manager.time import utc_now
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.site import Site
from envoy.server.settings import settings

# Valid site_ids for end_devices start 1 and increase
# Only a site_id of 0 is left, which we will use for the virtual end-device/site associated with the aggregator
VIRTUAL_END_DEVICE_SITE_ID = 0


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


async def get_virtual_site_for_aggregator(
    session: AsyncSession, aggregator_id: int, aggregator_lfdi: str
) -> Optional[Site]:
    """Returns a virtual site to represent the aggregator.

    Returns None if the aggregator isn't found.
    Raises ValueError if aggregator lfdi cannot be converted to an sfdi.
    """

    # Check if the aggregator exists
    aggregator: Optional[Aggregator] = await select_aggregator(session=session, aggregator_id=aggregator_id)
    if aggregator is None:
        return None

    # The virtual site shares attributes (e.g. timezone) with the first site under the aggregator.
    first_site_under_aggregator: Optional[Site] = await select_first_site_under_aggregator(
        session=session, aggregator_id=aggregator_id
    )

    timezone_id = first_site_under_aggregator.timezone_id if first_site_under_aggregator else settings.default_timezone

    # lfdi is hex string, convert to sfdi (integer)
    try:
        aggregator_sfdi = common.convert_lfdi_to_sfdi(lfdi=aggregator_lfdi)
    except ValueError:
        raise ValueError(f"Invalid aggregator LFDI. Cannot convert '{aggregator_lfdi}' to an SFDI.")

    # The aggregator doesn't have a changed time of it own.
    # Virtual sites will have a changed_time representing when they were requested.
    changed_time = utc_now()

    # Use a DeviceCategory with no categories set, which could never happen for a genuine end device
    # This can be used as a potential way to identity the virtual end device
    # Note that CSIP doesn't identify the device category that an aggregator should use
    # so no category/capability is a reasonable default
    device_category = DeviceCategory(0)

    # Since the site is virtual we create the Site in-place here and return it
    return Site(
        site_id=VIRTUAL_END_DEVICE_SITE_ID,
        lfdi=aggregator_lfdi,
        sfdi=aggregator_sfdi,
        changed_time=changed_time,
        created_time=changed_time,
        aggregator_id=aggregator_id,
        device_category=device_category,
        timezone_id=timezone_id,
    )


async def select_first_site_under_aggregator(session: AsyncSession, aggregator_id: int) -> Optional[Site]:
    """Selects the Site with the lowest site_id and aggregator_id. Returns None if a match isn't found"""
    stmt = select(Site).where(Site.aggregator_id == aggregator_id).limit(1).order_by(Site.site_id)
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_single_site_with_site_id(session: AsyncSession, site_id: int, aggregator_id: int) -> Optional[Site]:
    """Selects the unique Site with the specified site_id and aggregator_id. Returns None if a match isn't found"""
    stmt = select(Site).where((Site.aggregator_id == aggregator_id) & (Site.site_id == site_id))
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_single_site_with_sfdi(session: AsyncSession, sfdi: int, aggregator_id: int) -> Optional[Site]:
    """Selects the unique Site with the specified sfdi and aggregator_id. Returns None if a match isn't found"""
    stmt = select(Site).where((Site.aggregator_id == aggregator_id) & (Site.sfdi == sfdi))
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

    The current value (if any) for the site will be archived"""

    if aggregator_id != site.aggregator_id:
        raise ValueError(f"Specified aggregator_id {aggregator_id} mismatches site.aggregator_id {site.aggregator_id}")

    # "Save" any existing sites with the same data to the archive table
    await copy_rows_into_archive(
        session, Site, ArchiveSite, lambda q: q.where((Site.aggregator_id == aggregator_id) & (Site.sfdi == site.sfdi))
    )

    # Perform the upsert
    table = Site.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    stmt = psql_insert(Site).values(**{k: getattr(site, k) for k in update_cols})
    resp = await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[Site.aggregator_id, Site.sfdi],
            set_={k: getattr(stmt.excluded, k) for k in update_cols},
        ).returning(Site.site_id)
    )
    return resp.scalar_one()
