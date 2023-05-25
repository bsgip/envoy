from datetime import datetime, timezone
from typing import Optional

import envoy.server.schema.uri as uris
from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_mrid
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.schema.sep2.metering import Reading
from envoy.server.schema.sep2.metering_mirror import MirrorMeterReading, MirrorUsagePoint
from envoy.server.schema.sep2.types import QualityFlagsType, RoleFlagsType, ServiceKind

MIRROR_USAGE_POINT_MRID_PREFIX: int = int("f051", 16)


class MirrorUsagePointMapper:
    @staticmethod
    def map_from_request(
        mup: MirrorUsagePoint, aggregator_id: int, site_id: int, changed_time: datetime
    ) -> SiteReadingType:
        """Takes a MirrorUsagePoint, validates it and creates an equivalent SiteReadingType"""
        if not mup.mirrorMeterReadings or len(mup.mirrorMeterReadings) == 0:
            raise InvalidMappingError("Not MirrorMeterReading / ReadingType specified")
        rt = mup.mirrorMeterReadings[0].readingType

        if not rt:
            raise InvalidMappingError("ReadingType was not specified")
        if not rt.uom:
            raise InvalidMappingError("ReadingType.uom was not specified")

        return SiteReadingType(
            aggregator_id=aggregator_id,
            site_id=site_id,
            uom=rt.uom,
            data_qualifier=rt.dataQualifier,
            flow_direction=rt.flowDirection,
            accumulation_behaviour=rt.accumulationBehaviour,
            kind=rt.kind,
            phase=rt.phase,
            power_of_ten_multiplier=rt.powerOfTenMultiplier,
            default_interval_seconds=rt.intervalLength,
            changed_time=changed_time,
        )

    @staticmethod
    def map_to_response(srt: SiteReadingType, site: Site) -> MirrorUsagePoint:
        """Maps a SiteReadingType and associated Site into a MirrorUsagePoint"""

        return MirrorUsagePoint.validate(
            {
                "href": uris.MirrorUsagePointUri.format(mup_id=srt.site_reading_type_id),
                "deviceLFDI": site.lfdi,
                "postRate": None,
                "roleFlags": RoleFlagsType.NONE,
                "serviceCategoryKind": ServiceKind.ELECTRICITY,
                "status": 0,
                "mRID": generate_mrid(MIRROR_USAGE_POINT_MRID_PREFIX, srt.site_reading_type_id),
                "mirrorMeterReadings": [
                    {
                        "readingType": {
                            "accumulationBehaviour": srt.accumulation_behaviour,
                            "dataQualifier": srt.data_qualifier,
                            "flowDirection": srt.flow_direction,
                            "intervalLength": srt.default_interval_seconds,
                            "kind": srt.kind,
                            "phase": srt.phase,
                            "powerOfTenMultiplier": srt.power_of_ten_multiplier,
                            "uom": srt.uom,
                        }
                    }
                ],
            }
        )


class MirrorMeterReadingMapper:
    @staticmethod
    def map_reading_from_request(reading: Reading, site_reading_type_id: int, changed_time: datetime) -> SiteReading:
        """Maps a single Reading from a request to an equivalent SiteReading for site_reading_type_id"""
        quality_flags: QualityFlagsType
        if reading.qualityFlags:
            quality_flags = QualityFlagsType(int(reading.qualityFlags, 16))
        else:
            quality_flags = QualityFlagsType.NONE

        if reading.timePeriod is None:
            raise InvalidMappingError("Reading.timePeriod was not specified")

        return SiteReading(
            site_reading_type_id=site_reading_type_id,
            changed_time=changed_time,
            local_id=reading.localID,
            quality_flags=quality_flags,
            time_period_start=datetime.fromtimestamp(reading.timePeriod.start, timezone.utc),
            time_period_seconds=reading.timePeriod.duration,
            value=reading.value,
        )

    @staticmethod
    def map_from_request(
        mmr: MirrorMeterReading, aggregator_id: int, site_reading_type_id: int, changed_time: datetime
    ) -> list[SiteReading]:
        """Takes a set of MirrorMeterReading for a given site_reading_type and creates the equivalent set of
        SiteReading"""

        mrs = mmr.mirrorReadingSets
        if mrs is None:
            raise InvalidMappingError("No MirrorReadingSet specified")

        # we are trying to avoid concatenating a bunch of lists as we expect clients to normally only send a single
        # MirrorReadingSet per update - but that can't be guaranteed so this our compromise
        readings: Optional[list[SiteReading]] = None
        for mr in mrs:
            new_set = [
                MirrorMeterReadingMapper.map_reading_from_request(r, site_reading_type_id, changed_time)
                for r in mr.readings  # type: ignore [union-attr] # The if mr.readings prevent None from appearing here
                if mr.readings is not None
            ]
            if readings is None:
                readings = new_set
            else:
                readings = readings + new_set

        if readings is None:
            return []
        return readings
