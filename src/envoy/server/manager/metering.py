from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from tzlocal import get_localzone

from envoy.server.crud.end_device import select_single_site_with_lfdi
from envoy.server.crud.site_reading import upsert_site_reading_type_for_aggregator
from envoy.server.exception import InvalidIdError
from envoy.server.mapper.sep2.metering import MirrorUsagePointMapper
from envoy.server.schema.sep2.metering_mirror import MirrorUsagePoint, MirrorUsagePointListResponse


class MirrorMeteringManager:
    @staticmethod
    async def create_mirror_usage_point(
        session: AsyncSession, aggregator_id: int, mup: MirrorUsagePoint
    ) -> Optional[int]:
        """Creates a new mup (or fetches an existing one of the same value). Returns the Id associated with the created
        or updated mup. Raises InvalidIdError if the underlying site cannot be fetched"""
        site = await select_single_site_with_lfdi(session=session, lfdi=mup.deviceLFDI, aggregator_id=aggregator_id)
        if site is None:
            raise InvalidIdError("deviceLFDI doesn't match a known site for this aggregator")

        changed_time = datetime.now(tz=get_localzone())
        srt = MirrorUsagePointMapper.map_from_request(
            mup, aggregator_id=aggregator_id, site_id=site.site_id, changed_time=changed_time
        )

        srt_id = await upsert_site_reading_type_for_aggregator(
            session, aggregator_id=aggregator_id, site_reading_type=srt
        )
        await session.commit()
        return srt_id
