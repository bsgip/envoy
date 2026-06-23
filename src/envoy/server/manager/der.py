import logging
from datetime import datetime

from envoy_schema.server.schema.sep2.der import (
    DER,
    DERAvailability,
    DERCapability,
    DERListResponse,
    DERSettings,
    DERStatus,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.archive import copy_rows_into_archive
from envoy.server.crud.der import (
    select_der_changed_time_for_site,
    select_site_der_availability_for_site,
    select_site_der_rating_for_site,
    select_site_der_setting_for_site,
    select_site_der_status_for_site,
)
from envoy.server.crud.site import select_single_site_with_site_id
from envoy.server.exception import NotFoundError
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.manager.time import utc_now
from envoy.server.mapper.sep2.der import (
    DERAvailabilityMapper,
    DERCapabilityMapper,
    DERMapper,
    DERSettingMapper,
    DERStatusMapper,
)
from envoy.server.model.archive.site import (
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import SiteRequestScope

logger = logging.getLogger(__name__)


async def _site_for_der_or_raise(session: AsyncSession, aggregator_id: int, site_id: int) -> Site:
    """Fetches the Site backing the (single, virtual) DER for site_id. Raises NotFoundError if the site is
    missing / not accessible under aggregator_id."""
    site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)
    if site is None:
        raise NotFoundError(f"site with id {site_id} not found")
    return site


class DERManager:
    @staticmethod
    async def fetch_der_list_for_site(
        session: AsyncSession,
        scope: SiteRequestScope,
        start: int,
        limit: int,
        after: datetime,
    ) -> DERListResponse:
        """Provides a list view of DER for a specific site. Raises NotFoundError if DER/Site couldn't be accessed"""

        # CSIP-Aus models a single (virtual) DER per site - this list is always 0 or 1 elements
        site = await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)
        changed_time = await select_der_changed_time_for_site(session, site)

        der_site_ids: list[int]
        total: int
        if after > changed_time:
            der_site_ids = []
            total = 0
        elif start > 0 or limit < 1:
            der_site_ids = []
            total = 1
        else:
            der_site_ids = [scope.site_id]
            total = 1

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return DERMapper.map_to_list_response(scope, der_site_ids, total, config.derl_pollrate_seconds)

    @staticmethod
    async def fetch_der_for_site(
        session: AsyncSession,
        scope: SiteRequestScope,
        site_der_id: int,
    ) -> DER:
        """Fetches a single DER for a specific site. Raises NotFoundError if DER/Site couldn't be accessed"""

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        return DERMapper.map_to_response(scope, scope.site_id, None)


class DERCapabilityManager:
    @staticmethod
    async def fetch_der_capability_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERCapability:
        """Fetches a single DER Capability for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERCapability has been stored."""

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        site_der_rating = await select_site_der_rating_for_site(session, scope.site_id)
        if site_der_rating is None:
            raise NotFoundError(f"no DERCapability on record for DER {site_der_id} in site {scope.site_id}")

        return DERCapabilityMapper.map_to_response(scope, site_der_rating, scope.site_id)

    @staticmethod
    async def upsert_der_capability_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
        der_capability: DERCapability,
    ) -> None:
        """Handles creating/updating the DERCapability for the specified site der. Raises NotFoundError
        if the site/der can't be found"""

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        changed_time = utc_now()
        new_der_rating = DERCapabilityMapper.map_from_request(changed_time, der_capability)
        new_der_rating.site_id = scope.site_id

        existing = await select_site_der_rating_for_site(session, scope.site_id)
        if existing is None:
            session.add(new_der_rating)
        else:
            await copy_rows_into_archive(
                session,
                SiteDERRating,
                ArchiveSiteDERRating,
                lambda q: q.where(SiteDERRating.site_der_rating_id == existing.site_der_rating_id),
            )
            new_der_rating.site_der_rating_id = existing.site_der_rating_id
            await session.merge(new_der_rating)

        await NotificationManager.notify_changed_deleted_entities(
            session, SubscriptionResource.SITE_DER_RATING, changed_time
        )
        await session.commit()


class DERSettingsManager:
    @staticmethod
    async def fetch_der_settings_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERSettings:
        """Fetches a single DER Settings for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERSettings has been stored."""

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        site_der_setting = await select_site_der_setting_for_site(session, scope.site_id)
        if site_der_setting is None:
            raise NotFoundError(f"no DERSettings on record for DER {site_der_id} in site {scope.site_id}")

        return DERSettingMapper.map_to_response(scope, site_der_setting, scope.site_id)

    @staticmethod
    async def upsert_der_settings_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
        der_settings: DERSettings,
    ) -> None:
        """Handles creating/updating the DERSettings for the specified site der. Raises NotFoundError
        if the site/der can't be found"""

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        changed_time = utc_now()
        new_der_setting = DERSettingMapper.map_from_request(changed_time, der_settings)
        new_der_setting.site_id = scope.site_id

        existing = await select_site_der_setting_for_site(session, scope.site_id)
        if existing is None:
            session.add(new_der_setting)
        else:
            await copy_rows_into_archive(
                session,
                SiteDERSetting,
                ArchiveSiteDERSetting,
                lambda q: q.where(SiteDERSetting.site_der_setting_id == existing.site_der_setting_id),
            )
            new_der_setting.site_der_setting_id = existing.site_der_setting_id
            await session.merge(new_der_setting)

        await NotificationManager.notify_changed_deleted_entities(
            session, SubscriptionResource.SITE_DER_SETTING, changed_time
        )
        await session.commit()


class DERAvailabilityManager:
    @staticmethod
    async def fetch_der_availability_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERAvailability:
        """Fetches a single DER Availability for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERSettings has been stored."""

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        site_der_availability = await select_site_der_availability_for_site(session, scope.site_id)
        if site_der_availability is None:
            raise NotFoundError(f"no DERAvailability on record for DER {site_der_id} in site {scope.site_id}")

        return DERAvailabilityMapper.map_to_response(scope, site_der_availability, scope.site_id)

    @staticmethod
    async def upsert_der_availability_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
        der_availability: DERAvailability,
    ) -> None:
        """Handles creating/updating the DERAvailability for the specified site der. Raises NotFoundError
        if the site/der can't be found"""

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        changed_time = utc_now()
        new_der_availability = DERAvailabilityMapper.map_from_request(changed_time, der_availability)
        new_der_availability.site_id = scope.site_id

        existing = await select_site_der_availability_for_site(session, scope.site_id)
        if existing is None:
            session.add(new_der_availability)
        else:
            await copy_rows_into_archive(
                session,
                SiteDERAvailability,
                ArchiveSiteDERAvailability,
                lambda q: q.where(SiteDERAvailability.site_der_availability_id == existing.site_der_availability_id),
            )
            new_der_availability.site_der_availability_id = existing.site_der_availability_id
            await session.merge(new_der_availability)

        await NotificationManager.notify_changed_deleted_entities(
            session, SubscriptionResource.SITE_DER_AVAILABILITY, changed_time
        )
        await session.commit()


class DERStatusManager:
    @staticmethod
    async def fetch_der_status_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERStatus:
        """Fetches a single DER Status for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERSettings has been stored."""

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        site_der_status = await select_site_der_status_for_site(session, scope.site_id)
        if site_der_status is None:
            raise NotFoundError(f"no DERStatus on record for DER {site_der_id} in site {scope.site_id}")

        return DERStatusMapper.map_to_response(scope, site_der_status, scope.site_id)

    @staticmethod
    async def upsert_der_status_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
        der_status: DERStatus,
    ) -> None:
        """Handles creating/updating the DERStatus for the specified site der. Raises NotFoundError
        if the site/der can't be found"""

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        await _site_for_der_or_raise(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        changed_time = utc_now()
        new_der_status = DERStatusMapper.map_from_request(changed_time, der_status)
        new_der_status.site_id = scope.site_id

        existing = await select_site_der_status_for_site(session, scope.site_id)
        if existing is None:
            session.add(new_der_status)
        else:
            await copy_rows_into_archive(
                session,
                SiteDERStatus,
                ArchiveSiteDERStatus,
                lambda q: q.where(SiteDERStatus.site_der_status_id == existing.site_der_status_id),
            )
            new_der_status.site_der_status_id = existing.site_der_status_id
            await session.merge(new_der_status)

        await NotificationManager.notify_changed_deleted_entities(
            session, SubscriptionResource.SITE_DER_STATUS, changed_time
        )
        await session.commit()
