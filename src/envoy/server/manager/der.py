import logging
from datetime import datetime
from typing import Optional

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
from envoy.server.crud.der import generate_default_site_der, select_site_der_for_site
from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.exception import NotFoundError
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.manager.time import utc_now
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID
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
from envoy.server.model.site import SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import SiteRequestScope

logger = logging.getLogger(__name__)


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

        # If there isn't custom DER info already in place - return a default
        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)
        session.expunge(site_der)  # NOTE: modifying this instance so we remove it from session to avoid ORM conflicts.
        site_der.site_der_id = PUBLIC_SITE_DER_ID

        # Manually filter - we are forcing our single DER into a simple list
        ders: list[tuple[SiteDER, Optional[str]]]
        total: int
        if after > site_der.changed_time:
            ders = []
            total = 0
        elif start > 0 or limit < 1:
            ders = []
            total = 1
        else:
            ders = [(site_der, DOE_PROGRAM_ID)]
            total = 1

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return DERMapper.map_to_list_response(scope, ders, total, config.derl_pollrate_seconds)

    @staticmethod
    async def fetch_der_for_site(
        session: AsyncSession,
        scope: SiteRequestScope,
        site_der_id: int,
    ) -> DER:
        """Fetches a single DER for a specific site. Raises NotFoundError if DER/Site couldn't be accessed"""

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)
        site_der.site_der_id = PUBLIC_SITE_DER_ID

        return DERMapper.map_to_response(scope, site_der, DOE_PROGRAM_ID)


class DERCapabilityManager:

    @staticmethod
    async def fetch_der_capability_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERCapability:
        """Fetches a single DER Capability for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERCapability has been stored."""

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        if site_der.site_der_rating is None:
            raise NotFoundError(f"no DERCapability on record for DER {site_der_id} in site {scope.site_id}")

        site_der.site_der_id = PUBLIC_SITE_DER_ID
        site_der.site_der_rating.site_der_id = PUBLIC_SITE_DER_ID
        return DERCapabilityMapper.map_to_response(scope, site_der.site_der_rating, scope.site_id)

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

        changed_time = utc_now()
        new_der_rating = DERCapabilityMapper.map_from_request(changed_time, der_capability)

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)
        if site_der.site_der_id is None:
            # we are inserting a whole new DER and rating
            site_der.site_der_rating = new_der_rating
            session.add(site_der)
        elif site_der.site_der_rating is None:
            # we are inserting a new rating
            new_der_rating.site_der_id = site_der.site_der_id
            site_der.site_der_rating = new_der_rating
        else:
            # we are updating an existing rating
            site_der_rating_id = site_der.site_der_rating.site_der_rating_id
            await copy_rows_into_archive(
                session,
                SiteDERRating,
                ArchiveSiteDERRating,
                lambda q: q.where(SiteDERRating.site_der_rating_id == site_der_rating_id),
            )
            new_der_rating.site_der_id = site_der.site_der_id
            new_der_rating.site_der_rating_id = site_der.site_der_rating.site_der_rating_id
            await session.merge(new_der_rating)

        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE_DER_RATING, changed_time)


class DERSettingsManager:

    @staticmethod
    async def fetch_der_settings_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERSettings:
        """Fetches a single DER Settings for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERSettings has been stored."""

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        if site_der.site_der_setting is None:
            raise NotFoundError(f"no DERSettings on record for DER {site_der_id} in site {scope.site_id}")

        site_der.site_der_id = PUBLIC_SITE_DER_ID
        site_der.site_der_setting.site_der_id = PUBLIC_SITE_DER_ID
        return DERSettingMapper.map_to_response(scope, site_der.site_der_setting, scope.site_id)

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

        changed_time = utc_now()
        new_der_setting = DERSettingMapper.map_from_request(changed_time, der_settings)

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)
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
            site_der_setting_id = site_der.site_der_setting.site_der_setting_id
            await copy_rows_into_archive(
                session,
                SiteDERSetting,
                ArchiveSiteDERSetting,
                lambda q: q.where(SiteDERSetting.site_der_setting_id == site_der_setting_id),
            )

            new_der_setting.site_der_id = site_der.site_der_id
            new_der_setting.site_der_setting_id = site_der.site_der_setting.site_der_setting_id
            await session.merge(new_der_setting)

        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE_DER_SETTING, changed_time)


class DERAvailabilityManager:

    @staticmethod
    async def fetch_der_availability_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERAvailability:
        """Fetches a single DER Availability for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERSettings has been stored."""

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        if site_der.site_der_availability is None:
            raise NotFoundError(f"no DERAvailability on record for DER {site_der_id} in site {scope.site_id}")

        site_der.site_der_id = PUBLIC_SITE_DER_ID
        site_der.site_der_availability.site_der_id = PUBLIC_SITE_DER_ID
        return DERAvailabilityMapper.map_to_response(scope, site_der.site_der_availability, scope.site_id)

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

        changed_time = utc_now()
        new_der_availability = DERAvailabilityMapper.map_from_request(changed_time, der_availability)

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)
        if site_der.site_der_id is None:
            # we are inserting a whole new DER and availability
            site_der.site_der_availability = new_der_availability
            session.add(site_der)
        elif site_der.site_der_availability is None:
            # we are inserting a new availability
            new_der_availability.site_der_id = site_der.site_der_id
            site_der.site_der_availability = new_der_availability
        else:
            # we are updating an existing availability
            site_der_avail_id = site_der.site_der_availability.site_der_availability_id
            await copy_rows_into_archive(
                session,
                SiteDERAvailability,
                ArchiveSiteDERAvailability,
                lambda q: q.where(SiteDERAvailability.site_der_availability_id == site_der_avail_id),
            )

            new_der_availability.site_der_id = site_der.site_der_id
            new_der_availability.site_der_availability_id = site_der.site_der_availability.site_der_availability_id
            await session.merge(new_der_availability)

        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(
            SubscriptionResource.SITE_DER_AVAILABILITY, changed_time
        )


class DERStatusManager:

    @staticmethod
    async def fetch_der_status_for_site(
        session: AsyncSession,
        site_der_id: int,
        scope: SiteRequestScope,
    ) -> DERStatus:
        """Fetches a single DER Status for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERSettings has been stored."""

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {scope.site_id}")

        if site_der.site_der_status is None:
            raise NotFoundError(f"no DERStatus on record for DER {site_der_id} in site {scope.site_id}")

        site_der.site_der_id = PUBLIC_SITE_DER_ID
        site_der.site_der_status.site_der_id = PUBLIC_SITE_DER_ID
        return DERStatusMapper.map_to_response(scope, site_der.site_der_status, scope.site_id)

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

        changed_time = utc_now()
        new_der_status = DERStatusMapper.map_from_request(changed_time, der_status)

        site_der = await site_der_for_site(session, aggregator_id=scope.aggregator_id, site_id=scope.site_id)
        if site_der.site_der_id is None:
            # we are inserting a whole new DER and status
            site_der.site_der_status = new_der_status
            session.add(site_der)
        elif site_der.site_der_status is None:
            # we are inserting a new status
            new_der_status.site_der_id = site_der.site_der_id
            site_der.site_der_status = new_der_status
        else:
            # we are updating an existing status
            site_der_status_id = site_der.site_der_status.site_der_status_id
            await copy_rows_into_archive(
                session,
                SiteDERStatus,
                ArchiveSiteDERStatus,
                lambda q: q.where(SiteDERStatus.site_der_status_id == site_der_status_id),
            )

            new_der_status.site_der_id = site_der.site_der_id
            new_der_status.site_der_status_id = site_der.site_der_status.site_der_status_id
            await session.merge(new_der_status)

        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE_DER_STATUS, changed_time)
