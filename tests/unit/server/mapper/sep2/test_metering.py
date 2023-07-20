import unittest.mock as mock
from datetime import datetime

import envoy_schema.server.schema.uri as uris
import pytest
from envoy_schema.server.schema.sep2.metering import ReadingType
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
    UomType,
)

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.sep2.metering import MirrorUsagePointListMapper, MirrorUsagePointMapper
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReadingType
from tests.data.fake.generator import generate_class_instance


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
    srt_all_set.uom = UomType.FREQUENCY_HZ
    srt_all_set.accumulation_behaviour = AccumulationBehaviourType.CUMULATIVE
    srt_all_set.kind = KindType.DEMAND
    srt_all_set.phase = PhaseCode.PHASE_AN_S1N
    srt_all_set.data_qualifier = DataQualifierType.MAXIMUM
    srt_all_set.flow_direction = FlowDirectionType.FORWARD
    srt_optional: SiteReadingType = generate_class_instance(SiteReadingType, seed=303, optional_is_none=True)
    srt_optional.uom = UomType.REAL_POWER_WATT
    srt_optional.accumulation_behaviour = AccumulationBehaviourType.SUMMATION
    srt_optional.kind = KindType.CURRENCY
    srt_optional.phase = PhaseCode.NOT_APPLICABLE
    srt_optional.data_qualifier = DataQualifierType.AVERAGE
    srt_optional.flow_direction = FlowDirectionType.NOT_APPLICABLE

    result_all_set = MirrorUsagePointMapper.map_to_response(srt_all_set, site)
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

    result_optional = MirrorUsagePointMapper.map_to_response(srt_optional, site)
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

    mock_MirrorUsagePointMapper.map_to_response = mock.Mock(return_value=mapped_mup)

    result_all_set = MirrorUsagePointListMapper.map_to_list_response([srt_all_set], srt_count)
    assert result_all_set is not None
    assert isinstance(result_all_set, MirrorUsagePointListResponse)
    assert result_all_set.all_ == srt_count
    assert result_all_set.results == 1
    assert len(result_all_set.mirrorUsagePoints) == 1
    assert result_all_set.mirrorUsagePoints[0] == mapped_mup

    # Ensure we depend on the underlying individual entity map_to_response
    mock_MirrorUsagePointMapper.map_to_response.assert_called_once_with(srt_all_set, site)
