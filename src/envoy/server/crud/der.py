from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.exception import NotFoundError
from envoy.server.model.site import Site, SiteDER, SiteDERSetting


def generate_default_site_der(site_id: int, changed_time: datetime) -> SiteDER:
    """Generates a SiteDER that will act as a default empty DER placeholder. This is because CSIP requires
    DER to be pre populated - so if we have nothing in the DB - we instead generate an empty SiteDER

    Will leave primary key as None"""
    return SiteDER(
        site_id=site_id,
        changed_time=changed_time,
        site_der_rating=None,
        site_der_setting=None,
        site_der_availability=None,
        site_der_status=None,
    )


async def select_site_der_for_site(session: AsyncSession, aggregator_id: int, site_id: int) -> Optional[SiteDER]:
    """Selects the first SiteDER for site with ID under aggregator_id, returns None if it DNE. The selected SiteDER
    will have the SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus relationships included

    Designed for accessing a Single SiteDER for a site (as per csip aus requirements)"""

    stmt = (
        select(SiteDER)
        .where((SiteDER.site_id == site_id) & (Site.aggregator_id == aggregator_id))
        .join(Site)
        .order_by(SiteDER.site_der_id.desc())
        .limit(1)
        .options(
            selectinload(SiteDER.site_der_rating),
            selectinload(SiteDER.site_der_setting),
            selectinload(SiteDER.site_der_availability),
            selectinload(SiteDER.site_der_status),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def site_der_for_site(session: AsyncSession, aggregator_id: int, site_id: int) -> SiteDER:
    """Utility for fetching the SiteDER for the specified site. If nothing is in the database, returns the
    default site der.

    Will include downstream ratings/settings/availability/status if available

    Raises NotFoundError if site_id is missing / not accessible"""
    site_der = await select_site_der_for_site(session, site_id=site_id, aggregator_id=aggregator_id)
    if site_der is None:
        # Validate the site exists / is accessible first
        site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)
        if site is None:
            raise NotFoundError(f"site with id {site_id} not found")
        site_der = generate_default_site_der(site_id=site_id, changed_time=site.changed_time)

    return site_der


async def upsert_der_setting(
    session: AsyncSession, aggregator_id: int, site_id: int, new_der_setting: SiteDERSetting
) -> None:
    """Updates or inserts the specified SiteDERSetting for site_id, Any existing values overwritten will be archived.

    Can raise NotFoundError if the specified site_id is NOT accessible to this aggregator (or DNE)"""

    site_der = await site_der_for_site(session, aggregator_id=aggregator_id, site_id=site_id)
    if site_der.site_der_id is None:
        # we are inserting a whole new DER and settings
        site_der.site_der_setting = new_der_setting
        session.add(site_der)
    elif site_der.site_der_setting is None:
        # we are inserting a new setting
        new_der_setting.site_der_id = site_der.site_der_id
        site_der.site_der_setting = new_der_setting
    else:
        # we are updating an existing setting
        new_der_setting.site_der_id = site_der.site_der_id
        new_der_setting.site_der_setting_id = site_der.site_der_setting.site_der_setting_id
        await session.merge(new_der_setting)
