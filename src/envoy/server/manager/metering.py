import logging
from datetime import datetime

from envoy_schema.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.end_device import select_single_site_with_lfdi
from envoy.server.crud.site_reading import (
    count_site_reading_types_for_aggregator,
    delete_site_reading_type_for_aggregator,
    fetch_site_reading_type_for_aggregator,
    fetch_site_reading_types_page_for_aggregator,
    upsert_site_reading_type_for_aggregator,
    upsert_site_readings,
)
from envoy.server.exception import ForbiddenError, InvalidIdError, NotFoundError
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.manager.time import utc_now
from envoy.server.mapper.sep2.metering import (
    MirrorMeterReadingMapper,
    MirrorUsagePointListMapper,
    MirrorUsagePointMapper,
)
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import CertificateType, MUPRequestScope

logger = logging.getLogger(__name__)


class MirrorMeteringManager:
    @staticmethod
    async def create_or_update_mirror_usage_point(
        session: AsyncSession, scope: MUPRequestScope, mup: MirrorUsagePoint
    ) -> int:
        """Creates a new mup (or fetches an existing one of the same value). Returns the Id associated with the created
        or updated mup. Raises InvalidIdError if the underlying site cannot be fetched

        Will commit the underlying session on success"""

        mup_lfdi = mup.deviceLFDI.lower()  # Always compare on lowercase

        if scope.source == CertificateType.DEVICE_CERTIFICATE:
            # device certs are limited to the LFDI of the device cert
            if mup_lfdi != scope.lfdi:
                raise ForbiddenError(f"deviceLFDI '{mup.deviceLFDI}' doesn't match client certificate '{scope.lfdi}'")

        site = await select_single_site_with_lfdi(session=session, lfdi=mup_lfdi, aggregator_id=scope.aggregator_id)
        if site is None:
            raise InvalidIdError(f"deviceLFDI {mup.deviceLFDI} doesn't match a known site.")

        changed_time = utc_now()
        srt = MirrorUsagePointMapper.map_from_request(
            mup, aggregator_id=scope.aggregator_id, site_id=site.site_id, changed_time=changed_time
        )

        srt_id = await upsert_site_reading_type_for_aggregator(
            session=session, aggregator_id=scope.aggregator_id, site_reading_type=srt
        )
        await session.commit()

        logger.info(f"create_or_update_mirror_usage_point: upsert for site {site.site_id} site_reading_type {srt_id}")
        return srt_id

    @staticmethod
    async def fetch_mirror_usage_point(
        session: AsyncSession, scope: MUPRequestScope, site_reading_type_id: int
    ) -> MirrorUsagePoint:
        """Fetches a MirrorUsagePoint with the specified site_reading_type_id. Raises NotFoundError if it can't be
        located"""
        srt = await fetch_site_reading_type_for_aggregator(
            session=session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            site_reading_type_id=site_reading_type_id,
            include_site_relation=True,
        )
        if srt is None:
            raise NotFoundError(f"MirrorUsagePoint with id {site_reading_type_id} doesn't exist or is inaccessible")

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return MirrorUsagePointMapper.map_to_response(scope, srt, srt.site, config.mup_postrate_seconds)

    @staticmethod
    async def delete_mirror_usage_point(
        session: AsyncSession, scope: MUPRequestScope, site_reading_type_id: int
    ) -> bool:
        """Deletes the specified MUP (site reading type) and all child dependencies. Deleted records will be archived
        as necessary. Returns True if the delete removed something, False if the site DNE / is inaccessible.

        This will commit the transaction in session"""

        delete_time = utc_now()
        result = await delete_site_reading_type_for_aggregator(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            site_reading_type_id=site_reading_type_id,
            deleted_time=delete_time,
        )
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.READING, delete_time)

        return result

    @staticmethod
    async def add_or_update_readings(
        session: AsyncSession,
        scope: MUPRequestScope,
        site_reading_type_id: int,
        mmr: MirrorMeterReading,
    ) -> None:
        """Adds or updates a set of readings (updates based on start time) for a given site_reading_type (mup id)

        raises NotFoundError if the underlying site_reading_type_id DNE/doesn't belong to aggregator_id"""
        srt = await fetch_site_reading_type_for_aggregator(
            session=session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            site_reading_type_id=site_reading_type_id,
            include_site_relation=False,
        )
        if srt is None:
            raise NotFoundError(f"MirrorUsagePoint with id {site_reading_type_id} doesn't exist or is inaccessible")

        changed_time = utc_now()
        site_readings = MirrorMeterReadingMapper.map_from_request(
            mmr,
            aggregator_id=scope.aggregator_id,
            site_reading_type_id=site_reading_type_id,
            changed_time=changed_time,
        )

        await upsert_site_readings(session, changed_time, site_readings)
        await session.commit()
        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.READING, changed_time)
        return

    @staticmethod
    async def list_mirror_usage_points(
        session: AsyncSession, scope: MUPRequestScope, start: int, limit: int, changed_after: datetime
    ) -> MirrorUsagePointListResponse:
        """Fetches a paginated set of MirrorUsagePoint accessible to the specified aggregator"""
        srts = await fetch_site_reading_types_page_for_aggregator(
            session=session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            start=start,
            limit=limit,
            changed_after=changed_after,
        )

        count = await count_site_reading_types_for_aggregator(
            session=session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, changed_after=changed_after
        )

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return MirrorUsagePointListMapper.map_to_list_response(scope, srts, count, config.mup_postrate_seconds)
