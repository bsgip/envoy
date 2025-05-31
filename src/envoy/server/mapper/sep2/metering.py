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
from envoy.server.mapper.common import generate_href
from envoy.server.mapper.sep2.der import to_hex_binary
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.request_scope import BaseRequestScope

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
        if mup.roleFlags is None:
            role_flags = RoleFlagsType.NONE
        else:
            role_flags = int(mup.roleFlags, 16)

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
            role_flags=role_flags,
            changed_time=changed_time,
        )

    @staticmethod
    def map_to_response(
        scope: BaseRequestScope, srt: SiteReadingType, site: Site, postrate_seconds: int
    ) -> MirrorUsagePoint:
        """Maps a SiteReadingType and associated Site into a MirrorUsagePoint"""

        return MirrorUsagePoint.model_validate(
            {
                "href": generate_href(uris.MirrorUsagePointUri, scope, mup_id=srt.site_reading_type_id),
                "deviceLFDI": site.lfdi,
                "postRate": postrate_seconds,
                "roleFlags": to_hex_binary(srt.role_flags),
                "serviceCategoryKind": ServiceKind.ELECTRICITY,
                "status": 0,
                "mRID": MridMapper.encode_mirror_usage_point_mrid(scope, srt.site_reading_type_id),
                "mirrorMeterReadings": [
                    {
                        "mRID": MridMapper.encode_mirror_meter_reading_mrid(scope, srt.site_reading_type_id),
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
        scope: BaseRequestScope, srts: Sequence[SiteReadingType], srt_count: int, postrate_seconds: int
    ) -> MirrorUsagePointListResponse:
        """Maps a set of SiteReadingType (requires the associated site relationship being populated for each
        SiteReadingType)"""
        return MirrorUsagePointListResponse.model_validate(
            {
                "href": generate_href(uris.MirrorUsagePointListUri, scope),
                "all_": srt_count,
                "results": len(srts),
                "mirrorUsagePoints": [
                    MirrorUsagePointMapper.map_to_response(scope, srt, srt.site, postrate_seconds) for srt in srts
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
        readings: list[SiteReading] = []
        # If no MirrorReadingSet specified, check for a reading value to use, else return an error
        if mrs is None:
            if mmr.reading:
                readings = [
                    MirrorMeterReadingMapper.map_reading_from_request(mmr.reading, site_reading_type_id, changed_time)
                ]
                return readings
            else:
                raise InvalidMappingError("No MirrorReadingSet or Reading specified")

        if mmr.reading:
            raise InvalidMappingError("Both a reading and MirrorReadingList are specified. Please submit only one")

        for mr in mrs:
            readings.extend(
                MirrorMeterReadingMapper.map_reading_from_request(r, site_reading_type_id, changed_time)
                for r in mr.readings  # type: ignore [union-attr] # The if mr.readings prevent None from appearing here
            )

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
