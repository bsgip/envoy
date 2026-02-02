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

from envoy.server.crud.site_reading import GroupedSiteReadingTypeDetails
from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import CaseInsensitiveDict, generate_href
from envoy.server.mapper.sep2.der import to_hex_binary
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.request_scope import BaseRequestScope

READING_SET_ALL_ID = "all"  # string key identifying a reading set that includes ALL readings for MeterReading


class MirrorUsagePointMapper:
    @staticmethod
    def are_site_reading_types_equivalent(a: SiteReadingType, b: SiteReadingType) -> bool:
        """Checks if any updatable fields have different values across instances a and b.

        Returns True if the SiteReadingTypes are functionally identical"""

        return (
            a.uom == b.uom
            and a.flow_direction == b.flow_direction
            and a.data_qualifier == b.data_qualifier
            and a.accumulation_behaviour == b.accumulation_behaviour
            and a.kind == b.kind
            and a.phase == b.phase
            and a.power_of_ten_multiplier == b.power_of_ten_multiplier
            and a.default_interval_seconds == b.default_interval_seconds
            and a.commodity == b.commodity
        )

    @staticmethod
    def merge_site_reading_type(target: SiteReadingType, src: SiteReadingType, changed_time: datetime) -> bool:
        """Copies all the "updatable" fields from src into target (but only if different). If at least one field
        is copied across - changed_time will be applied to target.

        Updatable fields are those on ReadingType - roleFlags (exists on MUP), site/agg/mrid details are never copied

        Returns True if any fields are updated. False otherwise"""

        any_changes = False

        if target.uom != src.uom:
            any_changes = True
            target.uom = src.uom

        if target.flow_direction != src.flow_direction:
            any_changes = True
            target.flow_direction = src.flow_direction

        if target.data_qualifier != src.data_qualifier:
            any_changes = True
            target.data_qualifier = src.data_qualifier

        if target.accumulation_behaviour != src.accumulation_behaviour:
            any_changes = True
            target.accumulation_behaviour = src.accumulation_behaviour

        if target.kind != src.kind:
            any_changes = True
            target.kind = src.kind

        if target.phase != src.phase:
            any_changes = True
            target.phase = src.phase

        if target.power_of_ten_multiplier != src.power_of_ten_multiplier:
            any_changes = True
            target.power_of_ten_multiplier = src.power_of_ten_multiplier

        if target.default_interval_seconds != src.default_interval_seconds:
            any_changes = True
            target.default_interval_seconds = src.default_interval_seconds

        if target.commodity != src.commodity:
            any_changes = True
            target.commodity = src.commodity

        if target.version != src.version:
            any_changes = True
            target.version = src.version

        if target.description != src.description:
            any_changes = True
            target.description = src.description

        if any_changes:
            target.changed_time = changed_time

        return any_changes

    @staticmethod
    def extract_role_flags(mup: MirrorUsagePoint) -> RoleFlagsType:
        if not mup.roleFlags:
            return RoleFlagsType.NONE
        else:
            try:
                return RoleFlagsType(int(mup.roleFlags, 16))
            except Exception:
                raise InvalidMappingError(f"Unable to map {mup.roleFlags} to a RoleFlagsType")

    @staticmethod
    def map_from_request(
        mmr: MirrorMeterReading,
        aggregator_id: int,
        site_id: int,
        group_id: int,
        group_mrid: str,
        group_description: Optional[str],
        group_version: Optional[int],
        group_status: Optional[int],
        role_flags: RoleFlagsType,
        changed_time: datetime,
    ) -> SiteReadingType:
        """Takes a MirrorMeterReading, validates it and creates an equivalent SiteReadingType.

        Will raise an InvalidMappingError if mmr has no readingType"""

        rt = mmr.readingType
        if not rt:
            raise InvalidMappingError(f"No ReadingType specified on MirrorMeterReading {mmr.mRID}")

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

        if len(mmr.mRID) > 32:
            raise InvalidMappingError(f"mrid {mmr.mRID} is too long (should be 32 chars)")

        if len(group_mrid) > 32:
            raise InvalidMappingError(f"group mrid {mmr.mRID} is too long (should be 32 chars)")

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
            mrid=mmr.mRID,
            description=mmr.description,
            version=mmr.version,
            commodity=rt.commodity,
            group_id=group_id,
            group_mrid=group_mrid,
            group_description=group_description,
            group_version=group_version,
            group_status=group_status,
        )

    @staticmethod
    def map_to_response(
        scope: BaseRequestScope,
        group: GroupedSiteReadingTypeDetails,
        srts: Sequence[SiteReadingType],
        postrate_seconds: int,
    ) -> MirrorUsagePoint:
        """Maps a set of SiteReadingTypes with a common group into a MirrorUsagePoint"""

        return MirrorUsagePoint.model_validate(
            {
                "href": generate_href(uris.MirrorUsagePointUri, scope, mup_id=group.group_id),
                "deviceLFDI": group.site_lfdi,
                "postRate": postrate_seconds,
                "roleFlags": to_hex_binary(group.role_flags),
                "serviceCategoryKind": ServiceKind.ELECTRICITY,
                "status": 0 if group.group_status is None else group.group_status,
                "description": group.group_description,
                "version": group.group_version,
                "mRID": group.group_mrid,
                "mirrorMeterReadings": [
                    {
                        "mRID": srt.mrid,
                        "description": srt.description,
                        "version": srt.version,
                        "readingType": {
                            "accumulationBehaviour": srt.accumulation_behaviour,
                            "dataQualifier": srt.data_qualifier,
                            "flowDirection": srt.flow_direction,
                            "intervalLength": srt.default_interval_seconds,
                            "kind": srt.kind,
                            "phase": srt.phase,
                            "powerOfTenMultiplier": srt.power_of_ten_multiplier,
                            "uom": srt.uom,
                            "commodity": srt.commodity,
                        },
                    }
                    for srt in srts
                ],
            }
        )


class MirrorUsagePointListMapper:
    @staticmethod
    def map_to_list_response(
        scope: BaseRequestScope,
        group_count: int,
        grouped_srts: list[tuple[GroupedSiteReadingTypeDetails, Sequence[SiteReadingType]]],
        postrate_seconds: int,
    ) -> MirrorUsagePointListResponse:
        """Maps a set of SiteReadingTypes, grouped under their parent group_id to a MirrorUsagePointList)"""
        return MirrorUsagePointListResponse.model_validate(
            {
                "href": generate_href(uris.MirrorUsagePointListUri, scope),
                "all_": group_count,
                "results": len(grouped_srts),
                "pollRate": postrate_seconds,
                "mirrorUsagePoints": [
                    MirrorUsagePointMapper.map_to_response(scope, group, srts, postrate_seconds)
                    for group, srts in grouped_srts
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
        mmrs: list[MirrorMeterReading], srt_by_mrid: CaseInsensitiveDict[SiteReadingType], changed_time: datetime
    ) -> list[SiteReading]:
        """Takes a set of MirrorMeterReadings and generates SiteReading entries for every reading found. Those
        readings will be mapped to a SiteReadingType by mrid lookup into srt_by_mrid"""

        readings: list[SiteReading] = []

        for mmr in mmrs:
            srt = srt_by_mrid.get(mmr.mRID, None)
            if srt is None:
                raise InvalidMappingError(f"Couldn't map {mmr.mRID} to an existing SiteReadingType.")

            if mmr.reading:
                readings.append(
                    MirrorMeterReadingMapper.map_reading_from_request(
                        mmr.reading, srt.site_reading_type_id, changed_time
                    )
                )

            if mmr.mirrorReadingSets:
                for mrs in mmr.mirrorReadingSets:
                    if mrs.readings:
                        readings.extend(
                            (
                                MirrorMeterReadingMapper.map_reading_from_request(
                                    r, srt.site_reading_type_id, changed_time
                                )
                                for r in mrs.readings
                            )
                        )

        return readings

    @staticmethod
    def map_to_response(site_reading: SiteReading) -> Reading:
        """Takes a single site_reading and converts it to the equivalent sep2 Reading"""
        local_id: Optional[str] = to_hex_binary(site_reading.local_id) if site_reading.local_id is not None else None
        return Reading.model_validate(
            {
                "localID": local_id,
                "qualityFlags": to_hex_binary(site_reading.quality_flags),
                "timePeriod": {
                    "duration": site_reading.time_period_seconds,
                    "start": int(site_reading.time_period_start.timestamp()),
                },
                "value": site_reading.value,
            }
        )
