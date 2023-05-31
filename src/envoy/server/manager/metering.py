from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from tzlocal import get_localzone

from envoy.server.crud.end_device import select_single_site_with_lfdi
from envoy.server.crud.site_reading import (
    count_site_reading_types_for_aggregator,
    fetch_site_reading_type_for_aggregator,
    fetch_site_reading_types_page_for_aggregator,
    upsert_site_reading_type_for_aggregator,
    upsert_site_readings,
)
from envoy.server.exception import InvalidIdError, NotFoundError
from envoy.server.mapper.sep2.metering import MirrorMeterReadingMapper, MirrorUsagePointMapper
from envoy.server.schema.sep2.metering_mirror import MirrorMeterReading, MirrorUsagePoint, MirrorUsagePointListResponse


class MirrorMeteringManager:
    @staticmethod
    async def create_or_fetch_mirror_usage_point(
        session: AsyncSession, aggregator_id: int, mup: MirrorUsagePoint
    ) -> int:
        """Creates a new mup (or fetches an existing one of the same value). Returns the Id associated with the created
        or updated mup. Raises InvalidIdError if the underlying site cannot be fetched

        Will commit the underlying session on success"""
        site = await select_single_site_with_lfdi(session=session, lfdi=mup.deviceLFDI, aggregator_id=aggregator_id)
        if site is None:
            raise InvalidIdError("deviceLFDI doesn't match a known site for this aggregator")

        changed_time = datetime.now(tz=get_localzone())
        srt = MirrorUsagePointMapper.map_from_request(
            mup, aggregator_id=aggregator_id, site_id=site.site_id, changed_time=changed_time
        )

        srt_id = await upsert_site_reading_type_for_aggregator(
            session=session, aggregator_id=aggregator_id, site_reading_type=srt
        )
        await session.commit()
        return srt_id

    @staticmethod
    async def add_or_update_readings(
        session: AsyncSession, aggregator_id: int, site_reading_type_id: int, mmr: MirrorMeterReading
    ):
        """Adds or updates a set of readings (updates based on start time) for a given site_reading_type (mup id)

        raises NotFoundError if the underlying site_reading_type_id DNE/doesn't belong to aggregator_id"""
        srt = await fetch_site_reading_type_for_aggregator(
            session=session, aggregator_id=aggregator_id, site_reading_type_id=site_reading_type_id
        )
        if srt is None:
            raise NotFoundError(f"MirrorUsagePoint with id {site_reading_type_id} doesn't exist or is inaccessible")

        changed_time = datetime.now(tz=get_localzone())
        site_readings = MirrorMeterReadingMapper.map_from_request(
            mmr, aggregator_id=aggregator_id, site_reading_type_id=site_reading_type_id, changed_time=changed_time
        )

        await upsert_site_readings(session, site_readings)
        await session.commit()
        return

    @staticmethod
    async def list_mirror_usage_points(
        session: AsyncSession, aggregator_id: int, start: int, limit: int, changed_after: datetime
    ) -> MirrorUsagePointListResponse:
        """Fetches a paginated set of MirrorUsagePoint accessible to the specified aggregator"""
        srts = await fetch_site_reading_types_page_for_aggregator(
            session=session, aggregator_id=aggregator_id, start=start, limit=limit, changed_after=changed_after
        )

        count = await count_site_reading_types_for_aggregator(
            session=session, aggregator_id=aggregator_id, changed_after=changed_after
        )

        return MirrorUsagePointMapper.map_to_list_response(srts, count)
