from datetime import datetime, timezone
from typing import Optional, Sequence

import envoy_schema.server.schema.uri as uris
from envoy_schema.server.schema.sep2.metering import Reading
from envoy_schema.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
)
from envoy_schema.server.schema.sep2.types import (
    AccumulationBehaviourType,
    DataQualifierType,
    FlowDirectionType,
    KindType,
    PhaseCode,
    QualityFlagsType,
    RoleFlagsType,
    ServiceKind,
)

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href, generate_mrid
from envoy.server.mapper.sep2.der import to_hex_binary
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.request_state import RequestStateParameters

MIRROR_USAGE_POINT_MRID_PREFIX: int = int("f051", 16)
MIRROR_METER_READING_MRID_PREFIX: int = int("4ead", 16)

READING_SET_ALL_ID = "all"  # string key identifying a reading set that includes ALL readings for MeterReading


class MirrorUsagePointMapper:
    @staticmethod
    def map_from_request(
        mup: MirrorUsagePoint, aggregator_id: int, site_id: int, changed_time: datetime
    ) -> SiteReadingType:
        """Takes a MirrorUsagePoint, validates it and creates an equivalent SiteReadingType"""
        if not mup.mirrorMeterReadings or len(mup.mirrorMeterReadings) == 0:
            raise InvalidMappingError("No MirrorMeterReading / ReadingType specified")
        rt = mup.mirrorMeterReadings[0].readingType

        if not rt:
            raise InvalidMappingError("ReadingType was not specified")
        if not rt.uom:
            raise InvalidMappingError("ReadingType.uom was not specified")
        if rt.kind is None:
            kind = KindType.NOT_APPLICABLE
        else:
            kind = rt.kind
        if rt.phase is None:
            phase = PhaseCode.NOT_APPLICABLE
        else:
            phase = rt.phase
        if rt.powerOfTenMultiplier is None:
            power_of_ten_multiplier = 0
        else:
            power_of_ten_multiplier = rt.powerOfTenMultiplier
        if rt.dataQualifier is None:
            data_qualifier = DataQualifierType.NOT_APPLICABLE
        else:
            data_qualifier = rt.dataQualifier
        if rt.accumulationBehaviour is None:
            accumulation_behaviour = AccumulationBehaviourType.NOT_APPLICABLE
        else:
            accumulation_behaviour = rt.accumulationBehaviour
        if rt.flowDirection is None:
            flow_direction = FlowDirectionType.NOT_APPLICABLE
        else:
            flow_direction = rt.flowDirection
        if rt.intervalLength is None:
            default_interval_seconds = 0
        else:
            default_interval_seconds = rt.intervalLength

        return SiteReadingType(
            aggregator_id=aggregator_id,
            site_id=site_id,
            uom=rt.uom,
            data_qualifier=data_qualifier,
            flow_direction=flow_direction,
            accumulation_behaviour=accumulation_behaviour,
            kind=kind,
            phase=phase,
            power_of_ten_multiplier=power_of_ten_multiplier,
            default_interval_seconds=default_interval_seconds,
            changed_time=changed_time,
        )

    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, srt: SiteReadingType, site: Site) -> MirrorUsagePoint:
        """Maps a SiteReadingType and associated Site into a MirrorUsagePoint"""

        return MirrorUsagePoint.model_validate(
            {
                "href": generate_href(uris.MirrorUsagePointUri, rs_params, mup_id=srt.site_reading_type_id),
                "deviceLFDI": site.lfdi,
                "postRate": None,
                "roleFlags": to_hex_binary(RoleFlagsType.NONE),
                "serviceCategoryKind": ServiceKind.ELECTRICITY,
                "status": 0,
                "mRID": generate_mrid(MIRROR_USAGE_POINT_MRID_PREFIX, srt.site_reading_type_id),
                "mirrorMeterReadings": [
                    {
                        "mRID": generate_mrid(
                            MIRROR_USAGE_POINT_MRID_PREFIX, srt.site_reading_type_id, MIRROR_METER_READING_MRID_PREFIX
                        ),
                        "readingType": {
                            "accumulationBehaviour": srt.accumulation_behaviour,
                            "dataQualifier": srt.data_qualifier,
                            "flowDirection": srt.flow_direction,
                            "intervalLength": srt.default_interval_seconds,
                            "kind": srt.kind,
                            "phase": srt.phase,
                            "powerOfTenMultiplier": srt.power_of_ten_multiplier,
                            "uom": srt.uom,
                        },
                    }
                ],
            }
        )


class MirrorUsagePointListMapper:
    @staticmethod
    def map_to_list_response(
        rs_params: RequestStateParameters, srts: Sequence[SiteReadingType], srt_count: int
    ) -> MirrorUsagePointListResponse:
        """Maps a set of SiteReadingType (requires the associated site relationship being populated for each
        SiteReadingType)"""
        return MirrorUsagePointListResponse.model_validate(
            {
                "href": generate_href(uris.MirrorUsagePointListUri, rs_params),
                "all_": srt_count,
                "results": len(srts),
                "mirrorUsagePoints": [MirrorUsagePointMapper.map_to_response(rs_params, srt, srt.site) for srt in srts],
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

        if reading.localID is None:
            local_id = None
        else:
            local_id = int(reading.localID, 16)

        return SiteReading(
            site_reading_type_id=site_reading_type_id,
            changed_time=changed_time,
            local_id=local_id,
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

    @staticmethod
    def map_to_response(site_reading: SiteReading) -> Reading:
        """Takes a single site_reading and converts it to the equivalent sep2 Reading"""
        local_id: Optional[str] = f"{site_reading.local_id:0x}" if site_reading.local_id is not None else None
        return Reading.model_validate(
            {
                "localID": local_id,
                "qualityFlags": f"{int(site_reading.quality_flags):0x}",  # hex encoded
                "timePeriod": {
                    "duration": site_reading.time_period_seconds,
                    "start": int(site_reading.time_period_start.timestamp()),
                },
                "value": site_reading.value,
            }
        )
