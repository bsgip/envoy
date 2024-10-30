from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.site import Site, SiteDER


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
