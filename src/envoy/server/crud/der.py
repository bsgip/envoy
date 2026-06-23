from datetime import datetime

from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.site import (
    Site,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
)


async def select_site_der_rating_for_site(session: AsyncSession, site_id: int) -> SiteDERRating | None:
    """Selects the (single) SiteDERRating for a site, or None if it hasn't been set"""
    resp = await session.execute(select(SiteDERRating).where(SiteDERRating.site_id == site_id))
    return resp.scalar_one_or_none()


async def select_site_der_setting_for_site(session: AsyncSession, site_id: int) -> SiteDERSetting | None:
    """Selects the (single) SiteDERSetting for a site, or None if it hasn't been set"""
    resp = await session.execute(select(SiteDERSetting).where(SiteDERSetting.site_id == site_id))
    return resp.scalar_one_or_none()


async def select_site_der_availability_for_site(session: AsyncSession, site_id: int) -> SiteDERAvailability | None:
    """Selects the (single) SiteDERAvailability for a site, or None if it hasn't been set"""
    resp = await session.execute(select(SiteDERAvailability).where(SiteDERAvailability.site_id == site_id))
    return resp.scalar_one_or_none()


async def select_site_der_status_for_site(session: AsyncSession, site_id: int) -> SiteDERStatus | None:
    """Selects the (single) SiteDERStatus for a site, or None if it hasn't been set"""
    resp = await session.execute(select(SiteDERStatus).where(SiteDERStatus.site_id == site_id))
    return resp.scalar_one_or_none()


async def select_der_changed_time_for_site(session: AsyncSession, site: Site) -> datetime:
    """Returns the effective 'changed time' of the single (virtual) DER for a site - that is the most recent
    changed_time across any of its DER sub resources. Falls back to the site's own changed_time when no DER data
    has been recorded yet (i.e. the empty/default DER)."""
    changed_times = union_all(
        select(SiteDERRating.changed_time).where(SiteDERRating.site_id == site.site_id),
        select(SiteDERSetting.changed_time).where(SiteDERSetting.site_id == site.site_id),
        select(SiteDERAvailability.changed_time).where(SiteDERAvailability.site_id == site.site_id),
        select(SiteDERStatus.changed_time).where(SiteDERStatus.site_id == site.site_id),
    ).subquery()

    latest = (await session.execute(select(func.max(changed_times.c.changed_time)))).scalar()
    return latest if latest is not None else site.changed_time
