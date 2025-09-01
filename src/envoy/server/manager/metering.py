import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence, Union

from envoy_schema.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorMeterReadingListRequest,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
)
from envoy_schema.server.schema.sep2.types import RoleFlagsType
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
    fetch_site_reading_types_for_group_mrid,
    generate_site_reading_type_group_id,
    upsert_site_readings,
)
from envoy.server.exception import BadRequestError, ForbiddenError, InvalidIdError, NotFoundError
from envoy.server.manager.end_device import EndDeviceManager
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.manager.time import utc_now
from envoy.server.mapper.common import CaseInsensitiveDict
from envoy.server.mapper.sep2.metering import (
    MirrorMeterReadingMapper,
    MirrorUsagePointListMapper,
    MirrorUsagePointMapper,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReadingType
from envoy.server.model.site_reading import SiteReadingType
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import CertificateType, MUPListRequestScope, MUPRequestScope

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpsertMupResult:
    mup_id: int  # The ID of the MUP that was upserted
    created: bool  # True if created, False if updated


class MirrorMeteringManager:
    @staticmethod
    async def create_or_update_mirror_usage_point(
        session: AsyncSession, scope: MUPRequestScope, mup: MirrorUsagePoint
    ) -> UpsertMupResult:
        """Creates or updates a mup. Returns the Id associated with the created or updated mup.

        Raises InvalidIdError if the underlying site cannot be fetched

        Will commit the underlying session on success"""

        if scope.source == CertificateType.DEVICE_CERTIFICATE:
            # device certs are limited to the LFDI of the device cert
            if not EndDeviceManager.lfdi_matches(mup.deviceLFDI, scope.lfdi):
                raise ForbiddenError(f"deviceLFDI '{mup.deviceLFDI}' doesn't match client certificate '{scope.lfdi}'")

        if not mup.mirrorMeterReadings:
            raise BadRequestError(f"MirrorUsagePoint {mup.mRID} has no mirrorMeterReadings.")

        site = await select_single_site_with_lfdi(
            session=session, lfdi=mup.deviceLFDI, aggregator_id=scope.aggregator_id
        )
        if site is None:
            raise InvalidIdError(f"deviceLFDI {mup.deviceLFDI} doesn't match a known site.")
        site_id = site.site_id
        role_flags = MirrorUsagePointMapper.extract_role_flags(mup)

        changed_time = utc_now()

        group_srts = await fetch_site_reading_types_for_group_mrid(
            session, aggregator_id=scope.aggregator_id, site_id=site_id, group_mrid=mup.mRID
        )
        srts_by_mrid: CaseInsensitiveDict[SiteReadingType] = CaseInsensitiveDict(
            ((srt.mrid, srt) for srt in group_srts)
        )

        # If this is a new MUP mrid - we can insert it as is
        if not group_srts:
            created = True
            group_id = await generate_site_reading_type_group_id(session)

            # Start by creating the site reading types and getting them in the database
            for mmr in mup.mirrorMeterReadings:
                srt = MirrorUsagePointMapper.map_from_request(
                    mmr=mmr,
                    aggregator_id=scope.aggregator_id,
                    site_id=site_id,
                    group_id=group_id,
                    group_mrid=mup.mRID,
                    role_flags=role_flags,
                    changed_time=changed_time,
                )
                session.add(srt)
                srts_by_mrid[srt.mrid] = srt
            await session.flush()  # Flush to ensure all of our new SiteReadingTypes are in the database (and have a PK)
        else:
            created = False
            group_id = group_srts[0].group_id

            # Certain properties exist at the MUP level - changing them will require updating ALL existing
            # SiteReadingTypes in the group
            if role_flags != group_srts[0].role_flags:
                group_srt_ids = [srt.site_reading_type_id for srt in group_srts]
                await copy_rows_into_archive(
                    session,
                    SiteReadingType,
                    ArchiveSiteReadingType,
                    lambda q: q.where(SiteReadingType.site_reading_type_id.in_(group_srt_ids)),
                )
                for srt in group_srts:
                    srt.role_flags = role_flags
                await session.flush()

        await MirrorMeteringManager.sync_mirror_meter_readings(
            session,
            scope=scope,
            mmrs=mup.mirrorMeterReadings,
            srts_by_mrid=srts_by_mrid,
            site_id=site.site_id,
            group_id=group_id,
            role_flags=role_flags,
            group_mrid=mup.mRID,
        )
        await session.commit()

        logger.info(f"MUP Upsert for site {site_id} group_id {group_id}. Created {created}")
        return UpsertMupResult(mup_id=group_id, created=created)

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
        group_mrid = srts[0].group_mrid  # We know that these will be shared across all SiteReadingTypes under a group

        site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=scope.aggregator_id)
        if site is None:
            # This really shouldn't be happening under normal circumstances
            raise NotFoundError(f"MirrorUsagePoint with id {mup_id} doesn't exist or is inaccessible (bad site)")

        # We can construct a group from the site / other data we fetched
        group = GroupedSiteReadingTypeDetails(
            group_id=mup_id,
            group_mrid=group_mrid,
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
        srts_by_mrid: CaseInsensitiveDict[SiteReadingType] = CaseInsensitiveDict(((srt.mrid, srt) for srt in srts))

        role_flags = srts[0].role_flags  # We will always copy these across the group
        site_id = srts[0].site_id  # We will always copy these across the group
        group_mrid = srts[0].group_mrid  # We will always copy these across the group

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

        await MirrorMeteringManager.sync_mirror_meter_readings(
            session,
            scope=scope,
            mmrs=mmrs,
            srts_by_mrid=srts_by_mrid,
            site_id=site_id,
            group_id=mup_id,
            role_flags=role_flags,
            group_mrid=group_mrid,
        )

    @staticmethod
    async def list_mirror_usage_points(
        session: AsyncSession, scope: MUPListRequestScope, start: int, limit: int, changed_after: datetime
    ) -> MirrorUsagePointListResponse:
        """Fetches a paginated set of MirrorUsagePoint accessible to the specified aggregator"""

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        site_id: Optional[int]
        if scope.source == CertificateType.AGGREGATOR_CERTIFICATE:
            site_id = None  # No scoping required
        else:
            # This is now a device certificate
            if scope.device_site_id is None:
                # This is a special case - return an empty list if there isn't anything registered for this site
                return MirrorUsagePointListMapper.map_to_list_response(scope, 0, [], config.mup_postrate_seconds)
            else:
                site_id = scope.device_site_id

        # Start by fetching the top level MirrorUsagePoint info
        groups = await fetch_grouped_site_reading_details(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=site_id,
            start=start,
            changed_after=changed_after,
            limit=limit,
        )

        groups_count = await count_grouped_site_reading_details(
            session, aggregator_id=scope.aggregator_id, site_id=site_id, changed_after=changed_after
        )

        # Now fetch the MirrorMeterReading data for the above groups
        grouped_site_reading_types: list[tuple[GroupedSiteReadingTypeDetails, Sequence[SiteReadingType]]] = []
        for group in groups:
            srts = await fetch_site_reading_types_for_group(
                session, aggregator_id=scope.aggregator_id, site_id=site_id, group_id=group.group_id
            )
            grouped_site_reading_types.append((group, srts))

        return MirrorUsagePointListMapper.map_to_list_response(
            scope, groups_count, grouped_site_reading_types, config.mup_postrate_seconds
        )

    @staticmethod
    async def sync_mirror_meter_readings(
        session: AsyncSession,
        scope: MUPRequestScope,
        mmrs: list[MirrorMeterReading],
        srts_by_mrid: CaseInsensitiveDict[SiteReadingType],
        site_id: int,
        group_id: int,
        role_flags: RoleFlagsType,
        group_mrid: str,
    ) -> None:
        """Adds or updates a set of MirrorMeterReadings for a given group id. Expects every entry in
        srts_by_mrid to be flushed to the database (so they have a primary key set).

        Will also sync any descendent Readings

        raises NotFoundError if the underlying mups DNE/doesn't belong to aggregator_id"""

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
                mmr, scope.aggregator_id, site_id, group_id, group_mrid, role_flags, changed_time
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
                mmr, scope.aggregator_id, site_id, group_id, group_mrid, role_flags, changed_time
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
