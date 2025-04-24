from datetime import datetime
from typing import Optional, Sequence

from envoy_schema.server.schema.sep2.types import DeviceCategory
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud import common
from envoy.server.crud.aggregator import select_aggregator
from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.manager.time import utc_now
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import (
    ArchiveSite,
    ArchiveSiteDER,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.archive.subscription import ArchiveSubscription, ArchiveSubscriptionCondition
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import (
    Site,
    SiteDER,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
    SiteGroupAssignment,
)
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionCondition
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
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
        registration_pin=0,  # This is a nonsensical concept for the aggregator end device
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

    The site registration_pin will only be settable on insert. Attempts to update an existing registration_pin will
    be ignored.

    The current value (if any) for the site will be archived"""

    if aggregator_id != site.aggregator_id:
        raise ValueError(f"Specified aggregator_id {aggregator_id} mismatches site.aggregator_id {site.aggregator_id}")

    # "Save" any existing sites with the same data to the archive table
    await copy_rows_into_archive(
        session, Site, ArchiveSite, lambda q: q.where((Site.aggregator_id == aggregator_id) & (Site.sfdi == site.sfdi))
    )

    # Perform the upsert - remembering that we can only ever insert the registration_pin, never update it
    table = Site.__table__
    insert_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    update_cols = [c for c in insert_cols if c != Site.registration_pin.name]
    stmt = psql_insert(Site).values(**{k: getattr(site, k) for k in insert_cols})
    resp = await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[Site.aggregator_id, Site.sfdi],
            set_={k: getattr(stmt.excluded, k) for k in update_cols},
        ).returning(Site.site_id)
    )
    return resp.scalar_one()


async def delete_site_for_aggregator(
    session: AsyncSession, aggregator_id: int, site_id: int, deleted_time: datetime
) -> bool:
    """Delete the specified site (belonging to aggregator_id) and all descendent FK references (eg DOEs, Prices,
    readings etc). All deleted rows will be archived

    Returns True if the site was removed, False otherwise"""

    # Cleanest way of deleting is to validate the site exists for this aggregator and then going wild removing
    # everything related to that site. Not every child record will have access to aggregator_id without a join
    site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)
    if site is None:
        return False

    # Reading Types/Readings are a little tricky - we have no site_id reference in site_reading
    # Instead we prefetch all the site_read_type_id's and use that to delete
    # Assumption - We shouldn't normally have more than 10-20 MUPs per site - if this gets us into trouble,
    #              we can always paginate this step
    mup_id_resp = await session.execute(
        (select(SiteReadingType.site_reading_type_id).where(SiteReadingType.site_id == site_id))
    )
    mup_ids_to_delete = mup_id_resp.scalars().all()
    await delete_rows_into_archive(
        session,
        SiteReading,
        ArchiveSiteReading,
        deleted_time,
        lambda q: q.where(SiteReading.site_reading_type_id.in_(mup_ids_to_delete)),
    )
    await delete_rows_into_archive(
        session,
        SiteReadingType,
        ArchiveSiteReadingType,
        deleted_time,
        lambda q: q.where(SiteReadingType.site_reading_type_id.in_(mup_ids_to_delete)),
    )

    # Subscriptions are similar to MUPs - need to discover all sub IDs to delete all sub conditions
    sub_id_resp = await session.execute(
        select(Subscription.subscription_id).where(Subscription.scoped_site_id == site_id)
    )
    sub_ids_to_delete = sub_id_resp.scalars().all()
    await delete_rows_into_archive(
        session,
        SubscriptionCondition,
        ArchiveSubscriptionCondition,
        deleted_time,
        lambda q: q.where(SubscriptionCondition.subscription_id.in_(sub_ids_to_delete)),
    )
    await delete_rows_into_archive(
        session,
        Subscription,
        ArchiveSubscription,
        deleted_time,
        lambda q: q.where(Subscription.subscription_id.in_(sub_ids_to_delete)),
    )

    # Cleanup prices
    # NOTE - The underlying index on TariffGeneratedRate includes tariff_id - if we want this to run efficiently,
    #        we need to include tariff_id in the WHERE clause otherwise we'll be forced into a full table scan.
    #        see: https://github.com/bsgip/envoy/issues/191
    all_tariff_ids = (await session.execute(select(Tariff.tariff_id))).scalars().all()
    await delete_rows_into_archive(
        session,
        TariffGeneratedRate,
        ArchiveTariffGeneratedRate,
        deleted_time,
        lambda q: q.where(
            (TariffGeneratedRate.tariff_id.in_(all_tariff_ids)) & (TariffGeneratedRate.site_id == site_id)
        ),
    )

    # Cleanup does
    await delete_rows_into_archive(
        session,
        DynamicOperatingEnvelope,
        ArchiveDynamicOperatingEnvelope,
        deleted_time,
        lambda q: q.where((DynamicOperatingEnvelope.site_id == site_id)),
    )

    # Cleanup DER - again, similar to MUPs/SUBs, we need the DER IDs first
    der_id_resp = await session.execute((select(SiteDER.site_der_id).where(SiteDER.site_id == site_id)))
    der_ids_to_delete = der_id_resp.scalars().all()
    await delete_rows_into_archive(
        session,
        SiteDERRating,
        ArchiveSiteDERRating,
        deleted_time,
        lambda q: q.where(SiteDERRating.site_der_id.in_(der_ids_to_delete)),
    )
    await delete_rows_into_archive(
        session,
        SiteDERSetting,
        ArchiveSiteDERSetting,
        deleted_time,
        lambda q: q.where(SiteDERSetting.site_der_id.in_(der_ids_to_delete)),
    )
    await delete_rows_into_archive(
        session,
        SiteDERStatus,
        ArchiveSiteDERStatus,
        deleted_time,
        lambda q: q.where(SiteDERStatus.site_der_id.in_(der_ids_to_delete)),
    )
    await delete_rows_into_archive(
        session,
        SiteDERAvailability,
        ArchiveSiteDERAvailability,
        deleted_time,
        lambda q: q.where(SiteDERAvailability.site_der_id.in_(der_ids_to_delete)),
    )
    await delete_rows_into_archive(
        session,
        SiteDER,
        ArchiveSiteDER,
        deleted_time,
        lambda q: q.where(SiteDER.site_der_id.in_(der_ids_to_delete)),
    )

    # Site Groups assignments aren't archived - we can delete them directly
    await session.execute(delete(SiteGroupAssignment).where(SiteGroupAssignment.site_id == site_id))

    # Finally delete the site
    await delete_rows_into_archive(
        session,
        Site,
        ArchiveSite,
        deleted_time,
        lambda q: q.where(Site.site_id == site_id),
    )
    return True
