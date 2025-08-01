from datetime import datetime, timezone
from typing import Optional

import envoy_schema.server.schema.uri as uris
import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.metering import Reading, ReadingType
from envoy_schema.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorReadingSet,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
)
from envoy_schema.server.schema.sep2.types import (
    AccumulationBehaviourType,
    DataQualifierType,
    DateTimeIntervalType,
    FlowDirectionType,
    KindType,
    PhaseCode,
    QualityFlagsType,
    RoleFlagsType,
    UomType,
)

from envoy.server.crud.site_reading import GroupedSiteReadingTypeDetails
from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.sep2.der import to_hex_binary
from envoy.server.mapper.sep2.metering import (
    MirrorMeterReadingMapper,
    MirrorUsagePointListMapper,
    MirrorUsagePointMapper,
)
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.request_scope import BaseRequestScope


@pytest.mark.parametrize(
    "mmr",
    [
        generate_class_instance(MirrorMeterReading, readingType=None),
        generate_class_instance(MirrorMeterReading, readingType=generate_class_instance(ReadingType, uom=None)),
    ],
)
def test_MirrorUsagePointMapper_map_from_request_no_uom(mmr: MirrorUsagePoint):
    """uom is an important field - test the various ways it can go missing"""
    aggregator_id = 123
    site_id = 456
    group_id = 789
    group_mrid = "abc123"
    changed_time = datetime.now()

    with pytest.raises(InvalidMappingError):
        MirrorUsagePointMapper.map_from_request(
            mmr, aggregator_id, site_id, group_id, group_mrid, RoleFlagsType.NONE, changed_time
        )


def test_MirrorUsagePointMapper_map_from_request_long_mrid():
    """mrid has a 32 character limit"""
    aggregator_id = 123
    site_id = 456
    group_id = 789
    group_mrid = "abc123"
    changed_time = datetime.now()
    mmr = generate_class_instance(
        MirrorMeterReading, mRID="a" * 33, readingType=generate_class_instance(ReadingType, uom=None)
    )

    with pytest.raises(InvalidMappingError):
        MirrorUsagePointMapper.map_from_request(
            mmr, aggregator_id, site_id, group_id, group_mrid, RoleFlagsType.NONE, changed_time
        )


def test_MirrorUsagePointMapper_map_from_request_long_group_mrid():
    """mrid has a 32 character limit"""
    aggregator_id = 123
    site_id = 456
    group_id = 789
    group_mrid = "a" * 33
    changed_time = datetime.now()
    mmr = generate_class_instance(
        MirrorMeterReading, mRID="abc", readingType=generate_class_instance(ReadingType, uom=None)
    )

    with pytest.raises(InvalidMappingError):
        MirrorUsagePointMapper.map_from_request(
            mmr, aggregator_id, site_id, group_id, group_mrid, RoleFlagsType.NONE, changed_time
        )


@pytest.mark.parametrize(
    "role_flags_str, expected",
    [
        ("05", RoleFlagsType.IS_MIRROR | RoleFlagsType.IS_PEV),
        (
            "0f",
            RoleFlagsType.IS_MIRROR
            | RoleFlagsType.IS_PREMISES_AGGREGATION_POINT
            | RoleFlagsType.IS_PEV
            | RoleFlagsType.IS_DER,
        ),
        (
            "0F",
            RoleFlagsType.IS_MIRROR
            | RoleFlagsType.IS_PREMISES_AGGREGATION_POINT
            | RoleFlagsType.IS_PEV
            | RoleFlagsType.IS_DER,
        ),
        ("", RoleFlagsType.NONE),
        (None, RoleFlagsType.NONE),
        ("not valid", None),
    ],
)
def test_MirrorUsagePointMapper_extract_role_flags(role_flags_str: Optional[str], expected: Optional[RoleFlagsType]):
    mup = generate_class_instance(MirrorUsagePoint, roleFlags=role_flags_str)
    if expected is None:
        with pytest.raises(InvalidMappingError):
            MirrorUsagePointMapper.extract_role_flags(mup)
    else:
        result = MirrorUsagePointMapper.extract_role_flags(mup)
        assert isinstance(result, RoleFlagsType)
        assert result == expected


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_MirrorUsagePointMapper_merge_site_reading_type_identical(optional_is_none: bool):
    target = generate_class_instance(SiteReadingType, seed=101, optional_is_none=optional_is_none)
    src = generate_class_instance(SiteReadingType, seed=101, optional_is_none=optional_is_none)
    changed_time = datetime(2022, 11, 3, tzinfo=timezone.utc)
    assert MirrorUsagePointMapper.merge_site_reading_type(target, src, changed_time) is False

    assert_class_instance_equality(
        SiteReadingType, target, generate_class_instance(SiteReadingType, seed=101, optional_is_none=optional_is_none)
    )


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_MirrorUsagePointMapper_are_site_reading_types_equivalent(optional_is_none: bool):
    a = generate_class_instance(SiteReadingType, seed=101, optional_is_none=optional_is_none)
    b = generate_class_instance(SiteReadingType, seed=101, optional_is_none=optional_is_none)
    c = generate_class_instance(SiteReadingType, seed=202, optional_is_none=optional_is_none)

    assert MirrorUsagePointMapper.are_site_reading_types_equivalent(a, b) is True
    assert MirrorUsagePointMapper.are_site_reading_types_equivalent(a, c) is False


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_MirrorUsagePointMapper_merge_site_reading_type_changes(optional_is_none: bool):
    mrid = "my-mrid"
    site_reading_type_id = 123
    agg_id = 456
    site_id = 789
    group_id = 1001
    group_mrid = "abc-123"
    created_time = datetime(2011, 2, 3, tzinfo=timezone.utc)
    target = generate_class_instance(
        SiteReadingType,
        seed=101,
        optional_is_none=optional_is_none,
        mrid=mrid,
        site_reading_type_id=site_reading_type_id,
        site_id=site_id,
        group_id=group_id,
        group_mrid=group_mrid,
        aggregator_id=agg_id,
        created_time=created_time,
    )
    src = generate_class_instance(SiteReadingType, seed=202, optional_is_none=optional_is_none)
    changed_time = datetime(2022, 11, 3, tzinfo=timezone.utc)
    assert MirrorUsagePointMapper.merge_site_reading_type(target, src, changed_time) is True

    assert_class_instance_equality(
        SiteReadingType,
        target,
        generate_class_instance(SiteReadingType, seed=202, optional_is_none=optional_is_none),
        ignored_properties={
            "changed_time",
            "aggregator_id",
            "site_reading_type_id",
            "site_id",
            "created_time",
            "group_id",
            "group_mrid",
            "mrid",
            "role_flags",
        },
    )
    assert target.changed_time == changed_time
    assert target.created_time == created_time
    assert target.mrid == mrid
    assert target.site_reading_type_id == site_reading_type_id
    assert target.aggregator_id == agg_id
    assert target.site_id == site_id
    assert target.group_id == group_id
    assert target.group_mrid == group_mrid


def test_MirrorUsagePointMapper_map_from_request():
    """Tests map_from_request doesn't raise any obvious errors"""
    aggregator_id = 123
    site_id = 456
    group_id = 789
    group_mrid = "abc123"
    changed_time = datetime.now()
    role_flags = RoleFlagsType.IS_PEV
    mmr_all_set = generate_class_instance(MirrorMeterReading, seed=202)
    mmr_all_set.readingType = generate_class_instance(
        ReadingType, seed=303, optional_is_none=False, uom=UomType.APPARENT_POWER_VA
    )

    mmr_optional = generate_class_instance(MirrorMeterReading, seed=505)
    mmr_optional.readingType = generate_class_instance(ReadingType, seed=606, optional_is_none=True, uom=UomType.JOULES)

    result_all_set = MirrorUsagePointMapper.map_from_request(
        mmr_all_set, aggregator_id, site_id, group_id, group_mrid, role_flags, changed_time
    )
    assert result_all_set is not None
    assert isinstance(result_all_set, SiteReadingType)
    assert result_all_set.aggregator_id == aggregator_id
    assert result_all_set.site_id == site_id
    assert result_all_set.group_id == group_id
    assert result_all_set.group_mrid == group_mrid
    assert result_all_set.mrid == mmr_all_set.mRID
    assert result_all_set.changed_time == changed_time
    assert result_all_set.uom == UomType.APPARENT_POWER_VA
    assert result_all_set.power_of_ten_multiplier == mmr_all_set.readingType.powerOfTenMultiplier
    assert result_all_set.kind == mmr_all_set.readingType.kind
    assert result_all_set.phase == mmr_all_set.readingType.phase
    assert result_all_set.data_qualifier == mmr_all_set.readingType.dataQualifier
    assert result_all_set.accumulation_behaviour == mmr_all_set.readingType.accumulationBehaviour
    assert result_all_set.flow_direction == mmr_all_set.readingType.flowDirection
    assert result_all_set.default_interval_seconds == mmr_all_set.readingType.intervalLength
    assert result_all_set.role_flags == role_flags

    result_optional = MirrorUsagePointMapper.map_from_request(
        mmr_optional, aggregator_id, site_id, group_id, group_mrid, role_flags, changed_time
    )
    assert result_optional is not None
    assert isinstance(result_optional, SiteReadingType)
    assert result_optional.aggregator_id == aggregator_id
    assert result_optional.site_id == site_id
    assert result_optional.group_id == group_id
    assert result_optional.group_mrid == group_mrid
    assert result_optional.mrid == mmr_optional.mRID
    assert result_optional.changed_time == changed_time
    assert result_optional.uom == UomType.JOULES
    assert result_optional.power_of_ten_multiplier == 0, "Not set in mup_optional"
    assert result_optional.kind == KindType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.phase == PhaseCode.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.data_qualifier == DataQualifierType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.accumulation_behaviour == AccumulationBehaviourType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.flow_direction == FlowDirectionType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.default_interval_seconds == 0, "Not set in mup_optional"
    assert result_optional.role_flags == role_flags


def test_MirrorUsagePointMapper_map_to_response():
    """Tests that no exceptions are raised when mapping some common SiteReadingType's"""
    group = generate_class_instance(GroupedSiteReadingTypeDetails)
    srts = [
        generate_class_instance(SiteReadingType, seed=101, optional_is_none=False),
        generate_class_instance(SiteReadingType, seed=202, optional_is_none=True),
    ]

    href_prefix = "/abc/123"
    scope = generate_class_instance(BaseRequestScope, href_prefix=href_prefix, optional_is_none=True)
    post_rate_seconds = 1214
    result = MirrorUsagePointMapper.map_to_response(scope, group, srts, post_rate_seconds)

    assert result is not None
    assert isinstance(result, MirrorUsagePoint)
    assert result.href.startswith(href_prefix)
    assert result.href.endswith(uris.MirrorUsagePointUri.format(mup_id=group.group_id))
    assert isinstance(result.mRID, str)
    assert result.mRID == group.group_mrid
    assert result.mirrorMeterReadings
    assert len(result.mirrorMeterReadings) == len(srts)
    for mmr, srt in zip(result.mirrorMeterReadings, srts):
        assert mmr.mRID == srt.mrid
        assert mmr.readingType
        assert mmr.readingType.phase == srt.phase
        assert mmr.readingType.uom == srt.uom
        assert mmr.readingType.powerOfTenMultiplier == srt.power_of_ten_multiplier

    assert result.postRate == post_rate_seconds
    assert result.roleFlags == to_hex_binary(group.role_flags)


def test_MirrorUsagePointMapper_map_to_list_response():
    group_count = 252

    groups = [
        (
            generate_class_instance(GroupedSiteReadingTypeDetails, seed=101),
            [
                generate_class_instance(SiteReadingType, seed=202, optional_is_none=False),
                generate_class_instance(SiteReadingType, seed=303, optional_is_none=True),
            ],
        ),
        (
            generate_class_instance(GroupedSiteReadingTypeDetails, seed=404),
            [
                generate_class_instance(SiteReadingType, seed=505, optional_is_none=False),
            ],
        ),
    ]
    href_prefix = "/my/prefix"
    scope = generate_class_instance(BaseRequestScope, href_prefix=href_prefix)
    post_rate_seconds = 132

    result_all_set = MirrorUsagePointListMapper.map_to_list_response(scope, group_count, groups, post_rate_seconds)
    assert result_all_set is not None
    assert isinstance(result_all_set, MirrorUsagePointListResponse)
    assert result_all_set.href.startswith(href_prefix)
    assert result_all_set.all_ == group_count
    assert result_all_set.results == len(groups)
    assert len(result_all_set.mirrorUsagePoints) == len(groups)
    assert len(result_all_set.mirrorUsagePoints[0].mirrorMeterReadings) == 2
    assert len(result_all_set.mirrorUsagePoints[1].mirrorMeterReadings) == 1

    assert result_all_set.mirrorUsagePoints[0].deviceLFDI == groups[0][0].site_lfdi
    assert result_all_set.mirrorUsagePoints[1].deviceLFDI == groups[1][0].site_lfdi


def test_MirrorMeterReadingMapper_map_reading_from_request_no_time_period():
    """If TimePeriod is none - raise error"""
    reading: Reading = generate_class_instance(Reading)
    reading.timePeriod = None
    reading.qualityFlags = f"{QualityFlagsType.FORECAST:0x}"
    with pytest.raises(InvalidMappingError):
        MirrorMeterReadingMapper.map_reading_from_request(reading, 1, datetime.now())


def test_MirrorMeterReadingMapper_map_reading_from_request():
    """Sanity check that the parsing of common Reading values don't generate errors"""
    start_time = datetime(2022, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    reading_all_set: Reading = generate_class_instance(Reading, seed=101, optional_is_none=False)
    reading_all_set.qualityFlags = f"{QualityFlagsType.FORECAST:0x}"
    reading_all_set.localID = f"{3456:0x}"
    reading_all_set.timePeriod = generate_class_instance(DateTimeIntervalType)
    reading_all_set.timePeriod.duration = 123
    reading_all_set.timePeriod.start = int(start_time.timestamp())

    reading_optional: Reading = generate_class_instance(Reading, seed=202, optional_is_none=True)
    reading_optional.timePeriod = generate_class_instance(DateTimeIntervalType)
    reading_optional.timePeriod.duration = 123
    reading_optional.timePeriod.start = int(start_time.timestamp())

    changed_time = datetime.now()

    # reading: Reading, site_reading_type_id: int, changed_time: datetime
    result_all_set = MirrorMeterReadingMapper.map_reading_from_request(reading_all_set, 1, changed_time)
    assert result_all_set.value == reading_all_set.value
    assert result_all_set.site_reading_type_id == 1
    assert result_all_set.quality_flags == QualityFlagsType.FORECAST
    assert result_all_set.local_id == 3456
    assert result_all_set.changed_time == changed_time
    assert result_all_set.time_period_start == start_time
    assert result_all_set.time_period_seconds == 123

    result_optional = MirrorMeterReadingMapper.map_reading_from_request(reading_optional, 2, changed_time)
    assert result_optional.value == reading_optional.value
    assert result_optional.site_reading_type_id == 2
    assert result_optional.quality_flags == QualityFlagsType.NONE
    assert result_optional.local_id is None
    assert result_optional.changed_time == changed_time
    assert result_optional.time_period_start == start_time
    assert result_optional.time_period_seconds == 123


def test_MirrorMeterReadingMapper_map_from_request_empty_variants():
    mrid = "abc123"
    srt_map = {mrid: generate_class_instance(SiteReadingType)}
    changed_time = datetime(2011, 5, 6, 1, tzinfo=timezone.utc)

    assert_list_type(SiteReading, MirrorMeterReadingMapper.map_from_request([], srt_map, changed_time), 0)
    assert_list_type(
        SiteReading,
        MirrorMeterReadingMapper.map_from_request(
            [generate_class_instance(MirrorMeterReading, seed=101, optional_is_none=True, mRID=mrid)],
            srt_map,
            changed_time,
        ),
        0,
    )
    assert_list_type(
        SiteReading,
        MirrorMeterReadingMapper.map_from_request(
            [generate_class_instance(MirrorMeterReading, seed=101, mirrorReadingSets=[], reading=None, mRID=mrid)],
            srt_map,
            changed_time,
        ),
        0,
    )
    assert_list_type(
        SiteReading,
        MirrorMeterReadingMapper.map_from_request(
            [
                generate_class_instance(
                    MirrorMeterReading,
                    seed=101,
                    mRID=mrid,
                    mirrorReadingSets=[generate_class_instance(MirrorReadingSet, readings=None)],
                ),
                generate_class_instance(
                    MirrorMeterReading,
                    seed=101,
                    mRID=mrid,
                    mirrorReadingSets=[generate_class_instance(MirrorReadingSet, readings=[])],
                ),
            ],
            srt_map,
            changed_time,
        ),
        0,
    )


def test_MirrorMeterReadingMapper_map_from_request_bad_mrid():
    mrid = "abc123"
    srt_map = {mrid: generate_class_instance(SiteReadingType)}
    changed_time = datetime(2011, 5, 6, 1, tzinfo=timezone.utc)

    with pytest.raises(InvalidMappingError):
        MirrorMeterReadingMapper.map_from_request(
            [generate_class_instance(MirrorMeterReading, seed=101, optional_is_none=True, mRID=mrid + "foo")],
            srt_map,
            changed_time,
        )


def test_MirrorMeterReadingMapper_map_from_request():
    reading1 = generate_class_instance(
        Reading, seed=1, timePeriod=generate_class_instance(DateTimeIntervalType), optional_is_none=True
    )
    reading2 = generate_class_instance(
        Reading, seed=2, timePeriod=generate_class_instance(DateTimeIntervalType), optional_is_none=True
    )
    reading3 = generate_class_instance(
        Reading, seed=3, timePeriod=generate_class_instance(DateTimeIntervalType), optional_is_none=True
    )
    reading4 = generate_class_instance(
        Reading, seed=4, timePeriod=generate_class_instance(DateTimeIntervalType), optional_is_none=True
    )

    mrid1 = "abc123"
    mrid2 = "def456"

    srt_map = {
        mrid1: generate_class_instance(SiteReadingType, seed=101, site_reading_type_id=1),
        mrid2: generate_class_instance(SiteReadingType, seed=202, site_reading_type_id=2),
    }

    changed_time = datetime.now()

    mmrs = [
        generate_class_instance(MirrorMeterReading, seed=101, reading=reading1, mRID=mrid1),
        generate_class_instance(MirrorMeterReading, seed=202, reading=reading2, mRID=mrid2),
        generate_class_instance(
            MirrorMeterReading,
            seed=303,
            mirrorReadingSets=[generate_class_instance(MirrorReadingSet, readings=[])],
            mRID=mrid2,
        ),
        generate_class_instance(
            MirrorMeterReading,
            seed=404,
            mirrorReadingSets=[generate_class_instance(MirrorReadingSet, readings=[reading3, reading4])],
            mRID=mrid1,
        ),
    ]

    readings = MirrorMeterReadingMapper.map_from_request(mmrs, srt_map, changed_time)
    assert_list_type(SiteReading, readings, 4)

    assert [r.site_reading_type_id for r in readings] == [1, 2, 1, 1]
    assert [r.value for r in readings] == [reading1.value, reading2.value, reading3.value, reading4.value]


def test_MirrorMeterReadingMapper_map_to_response():
    """Sanity check on map_to_response generating valid models"""
    site_reading_all_set: SiteReading = generate_class_instance(SiteReading, seed=101, optional_is_none=False)
    site_reading_all_set.local_id = 255
    site_reading_optional: SiteReading = generate_class_instance(SiteReading, seed=202, optional_is_none=True)

    reading_all_set = MirrorMeterReadingMapper.map_to_response(site_reading_all_set)
    assert reading_all_set.value == site_reading_all_set.value
    assert reading_all_set.localID == "ff"
    assert isinstance(reading_all_set.qualityFlags, str)
    assert reading_all_set.timePeriod is not None
    assert reading_all_set.timePeriod.duration == site_reading_all_set.time_period_seconds
    assert reading_all_set.timePeriod.start == int(site_reading_all_set.time_period_start.timestamp())

    reading_optional = MirrorMeterReadingMapper.map_to_response(site_reading_optional)
    assert reading_optional.value == site_reading_optional.value
    assert reading_optional.localID is None
    assert isinstance(reading_optional.qualityFlags, str)
    assert reading_optional.timePeriod is not None
    assert reading_optional.timePeriod.duration == site_reading_optional.time_period_seconds
    assert reading_optional.timePeriod.start == int(site_reading_optional.time_period_start.timestamp())


def test_MirrorMeterReadingMapper_reading_round_trip():
    """Round trips a Reading via SiteReading to ensure everything (of importance) is preserved"""
    reading_orig: Reading = generate_class_instance(Reading)
    reading_orig.qualityFlags = f"{QualityFlagsType.FORECAST:0x}"
    reading_orig.localID = f"{3456:0x}"
    reading_orig.timePeriod = generate_class_instance(DateTimeIntervalType)
    reading_orig.timePeriod.duration = 123
    reading_orig.timePeriod.start = int(datetime(2024, 2, 3, 4, 5, 6).timestamp())

    site_reading = MirrorMeterReadingMapper.map_reading_from_request(reading_orig, 1, datetime.now())

    reading_roundtrip = MirrorMeterReadingMapper.map_to_response(site_reading)

    assert_class_instance_equality(
        Reading,
        reading_orig,
        reading_roundtrip,
        ignored_properties=set(["href", "type", "touTier", "subscribable", "consumptionBlock"]),
    )
