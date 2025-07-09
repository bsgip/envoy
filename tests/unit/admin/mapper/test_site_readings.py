from decimal import Decimal
from zoneinfo import ZoneInfo
import pytest
from datetime import datetime
from envoy.admin.mapper.site_reading import AdminSiteReadingMapper
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.site_reading import (
    CSIPAusSiteReading,
    CSIPAusSiteReadingPageResponse,
    CSIPAusSiteReadingUnit,
    PhaseEnum,
)
from envoy_schema.server.schema.sep2.types import UomType
from envoy_schema.server.schema.sep2.types import FlowDirectionType

TZ = ZoneInfo("Australia/Brisbane")


class MockSiteReadingType:
    """Mock SiteReadingType for testing"""

    def __init__(self, power_of_ten_multiplier: int, flow_direction: FlowDirectionType, phase: int):
        self.power_of_ten_multiplier = power_of_ten_multiplier
        self.flow_direction = flow_direction
        self.phase = phase


class MockSiteReading:
    """Mock SiteReading for testing"""

    def __init__(
        self, time_period_start: datetime, time_period_seconds: int, value: int, site_reading_type: MockSiteReadingType
    ):
        self.time_period_start = time_period_start
        self.time_period_seconds = time_period_seconds
        self.value = value
        self.site_reading_type = site_reading_type


def test_csip_unit_to_uom_mapping():
    mapped_uoms = []
    for reading_unit in CSIPAusSiteReadingUnit:
        uom = AdminSiteReadingMapper.csip_unit_to_uom(reading_unit)
        assert isinstance(uom, UomType)
        mapped_uoms.append(uom)
    assert len(mapped_uoms) == len(set(mapped_uoms)), "Every mapping should be unique"


def test_csip_unit_to_uom_invalid_unit():
    with pytest.raises(KeyError):
        AdminSiteReadingMapper.csip_unit_to_uom(999)


@pytest.mark.parametrize(
    "phase_code, expected_enum",
    [
        (0, PhaseEnum.NA),  # NA
        (129, PhaseEnum.AN),  # AN
        (65, PhaseEnum.BN),  # BN
        (33, PhaseEnum.CN),  # CN
        (999, PhaseEnum.NA),  # Unknown phase -> fallback to NA
    ],
)
def test_phase_code_mapping(phase_code: int, expected_enum: PhaseEnum):
    """Test phase code to PhaseEnum mapping including fallback"""
    mock_reading_type = generate_class_instance(
        SiteReadingType,
        power_of_ten_multiplier=0,
        flow_direction=FlowDirectionType.FORWARD,
        phase=phase_code,
    )

    mock_site_reading = generate_class_instance(
        SiteReading,
        time_period_start=datetime(2022, 6, 7, 1, 0, tzinfo=TZ),
        time_period_seconds=900,
        value=1000,
        site_reading_type=mock_reading_type,
    )

    result = AdminSiteReadingMapper.map_to_csip_aus_reading(mock_site_reading, CSIPAusSiteReadingUnit.ACTIVEPOWER)

    assert result.phase == expected_enum


@pytest.mark.parametrize(
    "raw_value, power_of_ten_multiplier, expected_value",
    [
        (5000, 0, Decimal("5000")),
        (5000, 3, Decimal("5000000")),
        (5000, -3, Decimal("5")),
        (0, 5, Decimal("0")),  # Zero value
    ],
)
def test_power_of_ten_multiplier(raw_value: int, power_of_ten_multiplier: int, expected_value: Decimal):
    """Test power of ten multiplier application"""
    mock_reading_type = generate_class_instance(
        SiteReadingType,
        power_of_ten_multiplier=power_of_ten_multiplier,
        flow_direction=FlowDirectionType.FORWARD,
        phase=0,
    )

    mock_site_reading = generate_class_instance(
        SiteReading,
        time_period_start=datetime(2022, 6, 7, 1, 0, tzinfo=TZ),
        time_period_seconds=900,
        value=raw_value,
        site_reading_type=mock_reading_type,
    )

    result = AdminSiteReadingMapper.map_to_csip_aus_reading(mock_site_reading, CSIPAusSiteReadingUnit.ACTIVEPOWER)

    assert result.value == expected_value


@pytest.mark.parametrize(
    "raw_value, flow_direction, expected_value",
    [
        (1000, FlowDirectionType.FORWARD, Decimal("1000")),  # Positive (import from grid)
        (1000, FlowDirectionType.REVERSE, Decimal("-1000")),  # Negative (export to grid)
        (0, FlowDirectionType.FORWARD, Decimal("0")),  # Zero
        (-500, FlowDirectionType.FORWARD, Decimal("-500")),  # Already negative
        (-500, FlowDirectionType.REVERSE, Decimal("500")),  # Double negative
    ],
)
def test_flow_direction_application(raw_value: int, flow_direction: FlowDirectionType, expected_value: Decimal):
    mock_reading_type = generate_class_instance(
        SiteReadingType,
        power_of_ten_multiplier=0,
        flow_direction=flow_direction,
        phase=0,
    )

    mock_site_reading = generate_class_instance(
        SiteReading,
        time_period_start=datetime(2022, 6, 7, 1, 0, tzinfo=TZ),
        time_period_seconds=900,
        value=raw_value,
        site_reading_type=mock_reading_type,
    )

    result = AdminSiteReadingMapper.map_to_csip_aus_reading(mock_site_reading, CSIPAusSiteReadingUnit.ACTIVEPOWER)

    assert result.value == expected_value


def test_map_to_csip_aus_reading_basic():
    mock_reading_type = generate_class_instance(
        SiteReadingType,
        power_of_ten_multiplier=0,
        flow_direction=FlowDirectionType.FORWARD,
        phase=65,  # BN phase
    )

    mock_site_reading = generate_class_instance(
        SiteReading,
        time_period_start=datetime(2022, 6, 7, 2, 15, 30, tzinfo=TZ),
        time_period_seconds=1800,  # 30 minutes
        value=2500,
        site_reading_type=mock_reading_type,
    )

    result = AdminSiteReadingMapper.map_to_csip_aus_reading(mock_site_reading, CSIPAusSiteReadingUnit.REACTIVEPOWER)

    assert isinstance(result, CSIPAusSiteReading)
    assert result.reading_start_time == datetime(2022, 6, 7, 2, 15, 30, tzinfo=TZ)
    assert result.duration_seconds == 1800
    assert result.phase == PhaseEnum.BN
    assert result.value == Decimal("2500")
    assert result.csip_aus_unit == CSIPAusSiteReadingUnit.REACTIVEPOWER


@pytest.mark.parametrize(
    "requested_unit",
    [
        CSIPAusSiteReadingUnit.ACTIVEPOWER,
        CSIPAusSiteReadingUnit.REACTIVEPOWER,
        CSIPAusSiteReadingUnit.FREQUENCY,
        CSIPAusSiteReadingUnit.VOLTAGE,
    ],
)
def test_map_to_csip_aus_reading_all_units(requested_unit: CSIPAusSiteReadingUnit):
    mock_reading_type = generate_class_instance(
        SiteReadingType,
        power_of_ten_multiplier=1,
        flow_direction=FlowDirectionType.FORWARD,
        phase=33,  # CN phase
    )

    mock_site_reading = generate_class_instance(
        SiteReading,
        time_period_start=datetime(2022, 6, 7, 1, 0, tzinfo=TZ),
        time_period_seconds=300,
        value=1500,
        site_reading_type=mock_reading_type,
    )

    result = AdminSiteReadingMapper.map_to_csip_aus_reading(mock_site_reading, requested_unit)

    assert result.csip_aus_unit == requested_unit
    assert result.value == Decimal("15000")  # 1500 * 10^1
    assert result.phase == PhaseEnum.CN


def test_map_to_csip_aus_reading_page_response_basic():
    # Create mock readings
    readings = [
        generate_class_instance(
            SiteReading,
            time_period_start=datetime(2022, 6, 7, 1, 0, tzinfo=TZ),
            time_period_seconds=900,
            value=1000,
            site_reading_type=MockSiteReadingType(0, FlowDirectionType.FORWARD, 129),
        ),
        generate_class_instance(
            SiteReading,
            time_period_start=datetime(2022, 6, 7, 2, 0, tzinfo=TZ),
            time_period_seconds=900,
            value=1100,
            site_reading_type=MockSiteReadingType(0, FlowDirectionType.FORWARD, 65),
        ),
    ]

    result = AdminSiteReadingMapper.map_to_csip_aus_reading_page_response(
        site_readings=readings,
        total_count=25,
        start=10,
        limit=50,
        site_id=42,
        start_time=datetime(2022, 6, 1, tzinfo=TZ),
        end_time=datetime(2022, 6, 30, tzinfo=TZ),
        requested_unit=CSIPAusSiteReadingUnit.ACTIVEPOWER,
    )

    assert isinstance(result, CSIPAusSiteReadingPageResponse)
    assert result.total_count == 25
    assert result.start == 10
    assert result.limit == 50
    assert result.site_id == 42
    assert result.start_time == datetime(2022, 6, 1, tzinfo=TZ)
    assert result.end_time == datetime(2022, 6, 30, tzinfo=TZ)
    assert len(result.readings) == 2

    # Verify each reading was transformed
    assert all(r.csip_aus_unit == CSIPAusSiteReadingUnit.ACTIVEPOWER for r in result.readings)
    assert result.readings[0].phase == PhaseEnum.AN
    assert result.readings[1].phase == PhaseEnum.BN


def test_map_to_csip_aus_reading_page_response_empty():
    result = AdminSiteReadingMapper.map_to_csip_aus_reading_page_response(
        site_readings=[],
        total_count=0,
        start=0,
        limit=100,
        site_id=123,
        start_time=datetime(2022, 1, 1, tzinfo=TZ),
        end_time=datetime(2022, 12, 31, tzinfo=TZ),
        requested_unit=CSIPAusSiteReadingUnit.VOLTAGE,
    )

    assert isinstance(result, CSIPAusSiteReadingPageResponse)
    assert result.total_count == 0
    assert len(result.readings) == 0
    assert result.site_id == 123
    assert result.start == 0
    assert result.limit == 100


def test_map_to_csip_aus_reading_page_response_large_dataset():
    """Test mapping with many readings"""
    readings = []
    for i in range(10):
        readings.append(
            MockSiteReading(
                time_period_start=datetime(2022, 6, 7, i, 0, tzinfo=TZ),
                time_period_seconds=3600,
                value=1000 + i * 100,
                site_reading_type=MockSiteReadingType(2, FlowDirectionType.REVERSE, 0),
            )
        )

    result = AdminSiteReadingMapper.map_to_csip_aus_reading_page_response(
        site_readings=readings,
        total_count=500,
        start=100,
        limit=10,
        site_id=999,
        start_time=datetime(2022, 6, 7, tzinfo=TZ),
        end_time=datetime(2022, 6, 8, tzinfo=TZ),
        requested_unit=CSIPAusSiteReadingUnit.FREQUENCY,
    )

    assert len(result.readings) == 10
    assert result.total_count == 500
    assert result.start == 100
    assert result.limit == 10

    # Verify transformations applied to all readings
    for i, reading in enumerate(result.readings):
        expected_value = Decimal(str((1000 + i * 100) * 100 * -1))  # 10^2 multiplier, reverse flow
        assert reading.value == expected_value
        assert reading.phase == PhaseEnum.NA
        assert reading.csip_aus_unit == CSIPAusSiteReadingUnit.FREQUENCY
