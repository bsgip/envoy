import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, Union

from envoy_schema.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorMeterReadingListRequest,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.archive import copy_rows_into_archive
from envoy.server.crud.end_device import select_single_site_with_lfdi, select_single_site_with_site_id
from envoy.server.crud.site_reading import (
    GroupedSiteReadingTypeDetails,
    count_grouped_site_reading_details,
    delete_site_reading_type_group,
    fetch_grouped_site_reading_details,
    fetch_site_reading_types_for_group,
    upsert_site_reading_type_for_aggregator,
    upsert_site_readings,
)
from envoy.server.exception import BadRequestError, ForbiddenError, InvalidIdError, NotFoundError
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.manager.time import utc_now
from envoy.server.mapper.sep2.metering import (
    MirrorMeterReadingMapper,
    MirrorUsagePointListMapper,
    MirrorUsagePointMapper,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReadingType
from envoy.server.model.site_reading import SiteReadingType
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import CertificateType, MUPRequestScope

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpsertMupResult:
    mup_id: int  # The ID of the MUP that was upserted
    created: bool  # True if created, False if updated


class MirrorMeteringManager:
    @staticmethod
    async def create_or_update_mirror_usage_point(
        session: AsyncSession, scope: MUPRequestScope, mup: MirrorUsagePoint
    ) -> int:
        """Creates or updates a mup. Returns the Id associated with the created or updated mup.

        Raises InvalidIdError if the underlying site cannot be fetched

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
    async def fetch_mirror_usage_point(session: AsyncSession, scope: MUPRequestScope, mup_id: int) -> MirrorUsagePoint:
        """Fetches a MirrorUsagePoint with the specified site_reading_type_id. Raises NotFoundError if it can't be
        located"""

        srts = await fetch_site_reading_types_for_group(
            session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, group_id=mup_id
        )
        if len(srts) == 0:
            raise NotFoundError(f"MirrorUsagePoint with id {mup_id} doesn't exist or is inaccessible")

        site_id = srts[0].site_id  # We can assume that all SiteReadingType's under a group share a site_id
        role_flags = srts[0].role_flags  # We know that these will be shared across all SiteReadingTypes under a group

        site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=scope.aggregator_id)
        if site is None:
            # This really shouldn't be happening under normal circumstances
            raise NotFoundError(f"MirrorUsagePoint with id {mup_id} doesn't exist or is inaccessible (bad site)")

        # We can construct a group from the site / other data we fetched
        group = GroupedSiteReadingTypeDetails(
            group_id=mup_id,
            site_id=site_id,
            site_lfdi=site.lfdi,
            role_flags=role_flags,
        )

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return MirrorUsagePointMapper.map_to_response(scope, group, srts, config.mup_postrate_seconds)

    @staticmethod
    async def delete_mirror_usage_point(session: AsyncSession, scope: MUPRequestScope, mup_id: int) -> bool:
        """Deletes the specified MUP (site reading types) and all child dependencies. Deleted records will be archived
        as necessary. Returns True if the delete removed something, False if the site DNE / is inaccessible.

        This will commit the transaction in session"""

        delete_time = utc_now()
        result = await delete_site_reading_type_group(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            group_id=mup_id,
            deleted_time=delete_time,
        )
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.READING, delete_time)

        return result

    @staticmethod
    async def add_or_update_readings(
        session: AsyncSession,
        scope: MUPRequestScope,
        mup_id: int,
        request: Union[MirrorMeterReading, MirrorMeterReadingListRequest],
    ) -> None:
        """Adds or updates a set of readings (updates based on start time) for a given mup id.

        raises NotFoundError if the underlying mups DNE/doesn't belong to aggregator_id"""
        srts = await fetch_site_reading_types_for_group(
            session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, group_id=mup_id
        )
        if not srts:
            raise NotFoundError(f"MirrorUsagePoint with id {mup_id} doesn't exist or is inaccessible")
        srts_by_mrid = {srt.mrid: srt for srt in srts}

        role_flags = srts[0].role_flags  # We will always copy these across the group
        site_id = srts[0].site_id  # We will always copy these across the group

        # Parse all the incoming MirrorMeterReadings - see if we need to update/insert any of our existing
        # SiteReadingTypes
        mmrs: list[MirrorMeterReading]
        if isinstance(request, MirrorMeterReadingListRequest):
            if not request.mirrorMeterReadings:
                # If the client sends us an empty list - there is literally nothing we can do
                raise BadRequestError(
                    f"MirrorMeterReadingListRequest sent to MirrorUsagePoint {mup_id} contained 0 mirroMeterReadings"
                )
            mmrs = request.mirrorMeterReadings
        else:
            mmrs = [request]

        mmrs_to_insert: list[MirrorMeterReading] = []
        mmrs_to_update: list[tuple[MirrorMeterReading, SiteReadingType]] = []
        for mmr in mmrs:
            matched_srt = srts_by_mrid.get(mmr.mRID, None)
            if matched_srt is None:
                # We have a new mrid
                if mmr.readingType is None:
                    raise BadRequestError(
                        f"MirrorMeterReading {mmr.mRID} has no readingType and doesn't match a prior MirrorMeterReading"
                    )
                mmrs_to_insert.append(mmr)
            else:
                # We have a type we've seen before
                if mmr.readingType:
                    mmrs_to_update.append((mmr, matched_srt))  # Don't update unless we have a ReadingType

        # Start applying the changes to the updating MMRs
        changed_time = utc_now()
        for mmr, target_srt in mmrs_to_update:
            src_srt = MirrorUsagePointMapper.map_from_request(
                mmr, scope.aggregator_id, site_id, mup_id, role_flags, changed_time
            )

            # We have to ensure we update in this order otherwise SQLALchemy will batch the operations in the wrong
            # order (which stuffs up our archive of the current values)
            if not MirrorUsagePointMapper.are_site_reading_types_equivalent(target_srt, src_srt):
                await copy_rows_into_archive(
                    session,
                    SiteReadingType,
                    ArchiveSiteReadingType,
                    lambda q: q.where(SiteReadingType.site_reading_type_id == target_srt.site_reading_type_id),
                )
                MirrorUsagePointMapper.merge_site_reading_type(target_srt, src_srt, changed_time)

        # Start inserting/updating the new site reading types
        for mmr in mmrs_to_insert:
            new_srt = MirrorUsagePointMapper.map_from_request(
                mmr, scope.aggregator_id, site_id, mup_id, role_flags, changed_time
            )
            session.add(new_srt)
            srts_by_mrid[mmr.mRID] = new_srt  # Log this new site reading type
        if mmrs_to_insert or mmrs_to_update:
            await session.flush()

        # Finally generate any site readings from the MMR's push them to the DB
        site_readings = MirrorMeterReadingMapper.map_from_request(mmrs, srts_by_mrid, changed_time)
        if site_readings:
            await upsert_site_readings(session, changed_time, site_readings)
        await session.commit()
        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.READING, changed_time)
        return

    @staticmethod
    async def list_mirror_usage_points(
        session: AsyncSession, scope: MUPRequestScope, start: int, limit: int, changed_after: datetime
    ) -> MirrorUsagePointListResponse:
        """Fetches a paginated set of MirrorUsagePoint accessible to the specified aggregator"""

        # Start by fetching the top level MirrorUsagePoint info
        groups = await fetch_grouped_site_reading_details(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            start=start,
            changed_after=changed_after,
            limit=limit,
        )

        groups_count = await count_grouped_site_reading_details(
            session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, changed_after=changed_after
        )

        # Now fetch the MirrorMeterReading data for the above groups
        grouped_site_reading_types: list[tuple[GroupedSiteReadingTypeDetails, Sequence[SiteReadingType]]] = []
        for group in groups:
            srts = await fetch_site_reading_types_for_group(
                session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, group_id=group.group_id
            )
            grouped_site_reading_types.append((group, srts))

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return MirrorUsagePointListMapper.map_to_list_response(
            scope, groups_count, grouped_site_reading_types, config.mup_postrate_seconds
        )
