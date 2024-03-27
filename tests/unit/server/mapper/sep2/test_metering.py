import unittest.mock as mock
from datetime import datetime, timezone

import envoy_schema.server.schema.uri as uris
import pytest
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
    UomType,
)

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.sep2.metering import (
    MirrorMeterReadingMapper,
    MirrorUsagePointListMapper,
    MirrorUsagePointMapper,
)
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.request_state import RequestStateParameters
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


def _no_uom_test_cases():
    mup_no_mmr: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, seed=101)
    mup_no_mmr.mirrorMeterReadings = None

    mup_empty_mmr: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, seed=202)
    mup_empty_mmr.mirrorMeterReadings = []

    mup_no_rt: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, seed=303)
    mup_no_rt.mirrorMeterReadings = [generate_class_instance(MirrorMeterReading, seed=505)]
    mup_no_rt.mirrorMeterReadings[0].readingType = None

    mup_no_uom: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, seed=606)
    mup_no_uom.mirrorMeterReadings = [generate_class_instance(MirrorMeterReading, seed=707)]
    mup_no_uom.mirrorMeterReadings[0].readingType = generate_class_instance(ReadingType, seed=808)
    mup_no_uom.mirrorMeterReadings[0].readingType.uom = None

    return [(mup_no_mmr), (mup_empty_mmr), (mup_no_rt), (mup_no_uom)]


@pytest.mark.parametrize("mup", _no_uom_test_cases())
def test_MirrorUsagePointMapper_map_from_request_no_uom(mup: MirrorUsagePoint):
    """uom is an important field - test the various ways it can go missing"""
    aggregator_id = 123
    site_id = 456
    changed_time = datetime.now()

    with pytest.raises(InvalidMappingError):
        MirrorUsagePointMapper.map_from_request(mup, aggregator_id, site_id, changed_time)


def test_MirrorUsagePointMapper_map_from_request():
    """Tests map_from_request doesn't raise any obvious errors"""
    aggregator_id = 123
    site_id = 456
    changed_time = datetime.now()
    mup_all_set: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, seed=101, optional_is_none=False)
    mup_all_set.mirrorMeterReadings = [generate_class_instance(MirrorMeterReading, seed=202)]
    mup_all_set.mirrorMeterReadings[0].readingType = generate_class_instance(
        ReadingType, seed=303, optional_is_none=False
    )
    mup_all_set.mirrorMeterReadings[0].readingType.uom = UomType.APPARENT_POWER_VA  # This must always be set

    mup_optional: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, seed=404, optional_is_none=True)
    mup_optional.mirrorMeterReadings = [generate_class_instance(MirrorMeterReading, seed=505)]
    mup_optional.mirrorMeterReadings[0].readingType = generate_class_instance(
        ReadingType, seed=606, optional_is_none=True
    )
    mup_optional.mirrorMeterReadings[0].readingType.uom = UomType.JOULES  # This must always be set

    result_all_set = MirrorUsagePointMapper.map_from_request(mup_all_set, aggregator_id, site_id, changed_time)
    assert result_all_set is not None
    assert isinstance(result_all_set, SiteReadingType)
    assert result_all_set.aggregator_id == aggregator_id
    assert result_all_set.site_id == site_id
    assert result_all_set.changed_time == changed_time
    assert result_all_set.uom == UomType.APPARENT_POWER_VA
    assert result_all_set.power_of_ten_multiplier == mup_all_set.mirrorMeterReadings[0].readingType.powerOfTenMultiplier
    assert result_all_set.kind == mup_all_set.mirrorMeterReadings[0].readingType.kind
    assert result_all_set.phase == mup_all_set.mirrorMeterReadings[0].readingType.phase
    assert result_all_set.data_qualifier == mup_all_set.mirrorMeterReadings[0].readingType.dataQualifier
    assert result_all_set.accumulation_behaviour == mup_all_set.mirrorMeterReadings[0].readingType.accumulationBehaviour
    assert result_all_set.flow_direction == mup_all_set.mirrorMeterReadings[0].readingType.flowDirection
    assert result_all_set.default_interval_seconds == mup_all_set.mirrorMeterReadings[0].readingType.intervalLength

    result_optional = MirrorUsagePointMapper.map_from_request(mup_optional, aggregator_id, site_id, changed_time)
    assert result_optional is not None
    assert isinstance(result_optional, SiteReadingType)
    assert result_optional.aggregator_id == aggregator_id
    assert result_optional.site_id == site_id
    assert result_optional.changed_time == changed_time
    assert result_optional.uom == UomType.JOULES
    assert result_optional.power_of_ten_multiplier == 0, "Not set in mup_optional"
    assert result_optional.kind == KindType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.phase == PhaseCode.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.data_qualifier == DataQualifierType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.accumulation_behaviour == AccumulationBehaviourType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.flow_direction == FlowDirectionType.NOT_APPLICABLE, "Not set in mup_optional"
    assert result_optional.default_interval_seconds == 0, "Not set in mup_optional"


def test_MirrorUsagePointMapper_map_to_response():
    """Tests that no exceptions are raised when mapping some common SiteReadingType's"""
    site: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    srt_all_set: SiteReadingType = generate_class_instance(SiteReadingType, seed=202, optional_is_none=False)
    srt_optional: SiteReadingType = generate_class_instance(SiteReadingType, seed=303, optional_is_none=True)
    rs_params = RequestStateParameters(1, None, None)

    result_all_set = MirrorUsagePointMapper.map_to_response(rs_params, srt_all_set, site)
    assert result_all_set is not None
    assert isinstance(result_all_set, MirrorUsagePoint)
    assert result_all_set.href == uris.MirrorUsagePointUri.format(mup_id=srt_all_set.site_reading_type_id)
    assert result_all_set.mRID != ""
    assert len(result_all_set.mirrorMeterReadings) == 1
    assert result_all_set.mirrorMeterReadings[0].mRID != result_all_set.mRID
    assert result_all_set.mirrorMeterReadings[0].readingType
    assert result_all_set.mirrorMeterReadings[0].readingType.phase == srt_all_set.phase
    assert result_all_set.mirrorMeterReadings[0].readingType.uom == srt_all_set.uom
    assert result_all_set.mirrorMeterReadings[0].readingType.powerOfTenMultiplier == srt_all_set.power_of_ten_multiplier

    result_optional = MirrorUsagePointMapper.map_to_response(rs_params, srt_optional, site)
    assert result_optional is not None
    assert isinstance(result_optional, MirrorUsagePoint)
    assert result_optional.href == uris.MirrorUsagePointUri.format(mup_id=srt_optional.site_reading_type_id)
    assert result_optional.mRID != ""
    assert len(result_optional.mirrorMeterReadings) == 1
    assert result_optional.mirrorMeterReadings[0].mRID != result_optional.mRID
    assert result_optional.mirrorMeterReadings[0].readingType
    assert result_optional.mirrorMeterReadings[0].readingType.phase == srt_optional.phase
    assert result_optional.mirrorMeterReadings[0].readingType.uom == srt_optional.uom
    assert (
        result_optional.mirrorMeterReadings[0].readingType.powerOfTenMultiplier == srt_optional.power_of_ten_multiplier
    )

    assert result_all_set.mRID != result_optional.mRID, "mrid should be unique"
    assert (
        result_all_set.mirrorMeterReadings[0].mRID != result_optional.mirrorMeterReadings[0].mRID
    ), "mrid should be unique"


@mock.patch("envoy.server.mapper.sep2.metering.MirrorUsagePointMapper")
def test_MirrorUsagePointMapper_map_to_list_response(mock_MirrorUsagePointMapper: mock.MagicMock):
    """Builds on the assumption that test_MirrorUsagePointMapper_map_to_response will cover the individual entity
    mapping. This just ensures the top level list properties are set correctly"""
    site: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    srt_count = 252
    srt_all_set: SiteReadingType = generate_class_instance(SiteReadingType, seed=202, optional_is_none=False)
    srt_all_set.site = site
    mapped_mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, seed=303)
    rs_params = RequestStateParameters(1, None, None)

    mock_MirrorUsagePointMapper.map_to_response = mock.Mock(return_value=mapped_mup)

    result_all_set = MirrorUsagePointListMapper.map_to_list_response(rs_params, [srt_all_set], srt_count)
    assert result_all_set is not None
    assert isinstance(result_all_set, MirrorUsagePointListResponse)
    assert result_all_set.all_ == srt_count
    assert result_all_set.results == 1
    assert len(result_all_set.mirrorUsagePoints) == 1
    assert result_all_set.mirrorUsagePoints[0] == mapped_mup

    # Ensure we depend on the underlying individual entity map_to_response
    mock_MirrorUsagePointMapper.map_to_response.assert_called_once_with(rs_params, srt_all_set, site)


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


def test_MirrorMeterReadingMapper_map_from_request():
    reading1: Reading = generate_class_instance(Reading, seed=1)
    reading1.timePeriod = generate_class_instance(DateTimeIntervalType)
    reading1.qualityFlags = None
    reading1.localID = None
    reading2: Reading = generate_class_instance(Reading, seed=2)
    reading2.timePeriod = generate_class_instance(DateTimeIntervalType)
    reading2.qualityFlags = None
    reading2.localID = None

    changed_time = datetime.now()

    mmr_all_set = generate_class_instance(MirrorMeterReading, seed=101, optional_is_none=False)
    mmr_all_set.mirrorReadingSets = [
        MirrorReadingSet.model_validate(
            {"mRID": "a", "timePeriod": generate_class_instance(DateTimeIntervalType), "readings": [reading1, reading2]}
        )
    ]
    mmr_optional = generate_class_instance(MirrorMeterReading, seed=202, optional_is_none=True)
    mmr_optional.mirrorReadingSets = [
        MirrorReadingSet.model_validate(
            {"mRID": "a", "timePeriod": generate_class_instance(DateTimeIntervalType), "readings": [reading1, reading2]}
        )
    ]
    mmr_split = generate_class_instance(MirrorMeterReading, seed=101, optional_is_none=False)
    mmr_split.mirrorReadingSets = [
        MirrorReadingSet.model_validate(
            {"mRID": "a", "timePeriod": generate_class_instance(DateTimeIntervalType), "readings": [reading1]}
        ),
        MirrorReadingSet.model_validate(
            {"mRID": "b", "timePeriod": generate_class_instance(DateTimeIntervalType), "readings": [reading2]}
        ),
    ]

    readings_all_set = MirrorMeterReadingMapper.map_from_request(mmr_all_set, 1, 2, changed_time)
    assert len(readings_all_set) == 2
    assert all([r.site_reading_type_id == 2 for r in readings_all_set])
    assert all([isinstance(r, SiteReading) for r in readings_all_set])

    readings_optional = MirrorMeterReadingMapper.map_from_request(mmr_optional, 3, 4, changed_time)
    assert len(readings_optional) == 2
    assert all([r.site_reading_type_id == 4 for r in readings_optional])
    assert all([isinstance(r, SiteReading) for r in readings_optional])

    readings_split = MirrorMeterReadingMapper.map_from_request(mmr_optional, 5, 6, changed_time)
    assert len(readings_split) == 2
    assert all([r.site_reading_type_id == 6 for r in readings_split])
    assert all([isinstance(r, SiteReading) for r in readings_split])


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
