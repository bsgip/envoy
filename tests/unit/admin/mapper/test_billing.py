from datetime import datetime, timezone
from decimal import Decimal

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import clone_class_instance, generate_class_instance
from envoy_schema.admin.schema.billing import (
    AggregatorBillingResponse,
    BillingDoe,
    BillingReading,
    BillingTariffRate,
    CalculationLogBillingResponse,
    SiteBillingResponse,
)
from envoy_schema.server.schema.sep2.types import AccumulationBehaviourType, DataQualifierType, FlowDirectionType

from envoy.admin.crud.billing import BillingData
from envoy.admin.mapper.billing import BillingMapper
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.log import CalculationLog
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.tariff import TariffGeneratedRate


@pytest.mark.parametrize(
    "value, power_of_ten, flow_direction, expected_value",
    [
        (1234, 3, FlowDirectionType.FORWARD, Decimal("1234000")),
        (1234, 3, FlowDirectionType.NOT_APPLICABLE, Decimal("1234000")),
        (1234, 3, FlowDirectionType.REVERSE, Decimal("-1234000")),
        (1234, 0, FlowDirectionType.FORWARD, Decimal("1234")),
        (1234, -3, FlowDirectionType.FORWARD, Decimal("1.234")),
        (1234, -3, FlowDirectionType.NOT_APPLICABLE, Decimal("1.234")),
        (1234, -3, FlowDirectionType.REVERSE, Decimal("-1.234")),
        (0, 0, FlowDirectionType.FORWARD, Decimal("0")),
        (0, 10, FlowDirectionType.FORWARD, Decimal("0")),
        (0, -10, FlowDirectionType.FORWARD, Decimal("0")),
        (0, -10, FlowDirectionType.REVERSE, Decimal("0")),
    ],
)
def test_map_reading_value_power_of_ten(
    value: int, power_of_ten: int, flow_direction: FlowDirectionType, expected_value: Decimal
):
    """Validates that power of ten is correctly applied when setting value"""
    reading: SiteReading = generate_class_instance(SiteReading, generate_relationships=True)
    reading.value = value
    reading.site_reading_type.power_of_ten_multiplier = power_of_ten
    reading.site_reading_type.flow_direction = flow_direction

    mapped = BillingMapper.map_reading(reading)

    assert isinstance(mapped, BillingReading)
    assert mapped.value == expected_value
    assert mapped.site_id == reading.site_reading_type.site_id
    assert mapped.period_start == reading.time_period_start
    assert mapped.duration_seconds == reading.time_period_seconds


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_reading_type_to_billing_primacy_all_unique(optional_is_none: bool):
    """Tests that all combos for reading_type_to_billing_primacy are unique integers (therefore they sort uniquely)"""

    all_srts: list[SiteReadingType] = []
    all_primacies: list[int] = []
    for dq in DataQualifierType:
        for ab in AccumulationBehaviourType:
            srt: SiteReadingType = generate_class_instance(
                SiteReadingType, optional_is_none=optional_is_none, data_qualifier=dq, accumulation_behaviour=ab
            )
            primacy = BillingMapper.reading_type_to_billing_primacy(srt)
            assert isinstance(primacy, int)

            alternative_primacy = BillingMapper.reading_type_to_billing_primacy(
                generate_class_instance(
                    SiteReadingType,
                    seed=1001,
                    optional_is_none=optional_is_none,
                    data_qualifier=dq,
                    accumulation_behaviour=ab,
                )
            )
            assert alternative_primacy == primacy, "Values should be consistent (based on data_qual and accum behavior)"

            all_srts.append(SiteReadingType)
            all_primacies.append(primacy)

    assert len(all_primacies) == len(all_srts)
    assert len(all_primacies) > 5, "Sanity check - if this fails then what are iterating over?"
    assert len(all_primacies) == len(set(all_primacies)), "All primacies should be unique integers"


SRT_PRIMACY_HIGHEST: SiteReadingType = generate_class_instance(
    SiteReadingType,
    data_qualifier=DataQualifierType.AVERAGE,
    accumulation_behaviour=AccumulationBehaviourType.SUMMATION,
)

SRT_PRIMACY_HIGH: SiteReadingType = generate_class_instance(
    SiteReadingType,
    data_qualifier=DataQualifierType.AVERAGE,
    accumulation_behaviour=AccumulationBehaviourType.NOT_APPLICABLE,
)

SRT_PRIMACY_LOW: SiteReadingType = generate_class_instance(
    SiteReadingType,
    data_qualifier=DataQualifierType.MINIMUM,
    accumulation_behaviour=AccumulationBehaviourType.INSTANTANEOUS,
)

SRT_PRIMACY_LOWEST: SiteReadingType = generate_class_instance(
    SiteReadingType,
    data_qualifier=DataQualifierType.NOT_APPLICABLE,
    accumulation_behaviour=AccumulationBehaviourType.NOT_APPLICABLE,
)


def test_reading_type_to_billing_primacy_sanity_check():
    """Tests that some "obvious" site types sort accordingly"""

    highest_srt = BillingMapper.reading_type_to_billing_primacy(SRT_PRIMACY_HIGHEST)
    high_srt = BillingMapper.reading_type_to_billing_primacy(SRT_PRIMACY_HIGH)
    low_srt = BillingMapper.reading_type_to_billing_primacy(SRT_PRIMACY_LOW)
    lowest_srt = BillingMapper.reading_type_to_billing_primacy(SRT_PRIMACY_LOWEST)

    assert highest_srt > high_srt
    assert high_srt > low_srt
    assert low_srt > lowest_srt


def gen_sr(value: int, srt: SiteReadingType) -> SiteReading:
    """Shorthand for generating a new SiteReading with the specified value/type"""
    return generate_class_instance(SiteReading, value=Decimal(value), site_reading_type=srt)


@pytest.mark.parametrize(
    "site_readings, expected_values",
    [
        ([], []),
        ([gen_sr(1, SRT_PRIMACY_HIGHEST)], [1]),
        ([gen_sr(2, SRT_PRIMACY_LOWEST)], [2]),
        ([gen_sr(2, SRT_PRIMACY_LOWEST), gen_sr(3, SRT_PRIMACY_HIGHEST)], [3]),
        ([gen_sr(1, SRT_PRIMACY_HIGHEST), gen_sr(2, SRT_PRIMACY_LOWEST)], [1]),
        ([gen_sr(1, SRT_PRIMACY_HIGHEST), gen_sr(2, SRT_PRIMACY_LOWEST), gen_sr(3, SRT_PRIMACY_HIGHEST)], [1, 3]),
        ([gen_sr(1, SRT_PRIMACY_LOWEST), gen_sr(2, SRT_PRIMACY_HIGHEST), gen_sr(3, SRT_PRIMACY_HIGHEST)], [2, 3]),
        ([gen_sr(1, SRT_PRIMACY_HIGHEST), gen_sr(2, SRT_PRIMACY_LOWEST), gen_sr(3, SRT_PRIMACY_HIGH)], [1]),
        (
            [
                gen_sr(1, SRT_PRIMACY_LOWEST),
                gen_sr(2, SRT_PRIMACY_LOWEST),
                gen_sr(3, SRT_PRIMACY_HIGH),
                gen_sr(4, SRT_PRIMACY_LOW),
                gen_sr(5, SRT_PRIMACY_HIGHEST),
            ],
            [5],
        ),
        (
            [
                gen_sr(1, SRT_PRIMACY_LOWEST),
                gen_sr(2, SRT_PRIMACY_LOWEST),
                gen_sr(3, SRT_PRIMACY_HIGH),
                gen_sr(4, SRT_PRIMACY_HIGH),
                gen_sr(5, SRT_PRIMACY_LOW),
                gen_sr(6, SRT_PRIMACY_LOW),
            ],
            [3, 4],
        ),
    ],
)
def test_choose_best_billing_readings(site_readings: list[SiteReading], expected_values: list[int]):
    """Tests that a known set of SiteReadings filter down to the highest primacy readings"""
    result = BillingMapper.choose_best_billing_readings(site_readings)
    assert_list_type(SiteReading, result, count=len(expected_values))
    assert expected_values == [int(r.value) for r in result]

    # Should also work with a reversed order too
    site_readings.reverse()
    expected_values.reverse()
    result_reversed = BillingMapper.choose_best_billing_readings(site_readings)
    assert_list_type(SiteReading, result_reversed, count=len(expected_values))
    assert expected_values == [int(r.value) for r in result_reversed]


TS_1 = datetime(2023, 1, 1, 1, 1, 1)
TS_2 = datetime(2023, 2, 2, 2, 2, 2)


@pytest.mark.parametrize(
    "expected_inputs, expected_outputs",
    [
        ([], []),  # Empty list
        ([(1, TS_1, 100, 1, SRT_PRIMACY_HIGHEST)], [(1, TS_1, Decimal("1000"))]),  # Singleton
        (
            [(1, TS_1, 100, 1, SRT_PRIMACY_HIGHEST), (1, TS_2, 100, 0, SRT_PRIMACY_HIGHEST)],
            [(1, TS_1, Decimal("1000")), (1, TS_2, Decimal("100"))],
        ),  # Multiple, no aggregation, variation on timestamp
        (
            [(1, TS_1, 1, 0, SRT_PRIMACY_HIGHEST), (2, TS_1, 2, 0, SRT_PRIMACY_HIGHEST)],
            [(1, TS_1, Decimal("1")), (2, TS_1, Decimal("2"))],
        ),  # Multiple, no aggregation, variation on site
        (
            [
                (1, TS_1, 1, -1, SRT_PRIMACY_HIGHEST),
                (1, TS_1, 2, -2, SRT_PRIMACY_HIGHEST),
                (1, TS_1, 3, -3, SRT_PRIMACY_HIGHEST),
            ],
            [(1, TS_1, Decimal("0.123"))],
        ),  # Multiple, aggregate everything
        (
            [
                (1, TS_1, 1, -1, SRT_PRIMACY_HIGHEST),
                (1, TS_1, 2, -2, SRT_PRIMACY_LOW),
                (1, TS_1, 3, -3, SRT_PRIMACY_HIGHEST),
            ],
            [(1, TS_1, Decimal("0.103"))],
        ),  # Multiple, aggregate everything but only take the "best" readings
        (
            [
                (1, TS_1, 1, -1, SRT_PRIMACY_LOWEST),
                (1, TS_1, 2, -2, SRT_PRIMACY_LOWEST),
                (1, TS_1, 3, -3, SRT_PRIMACY_LOWEST),
                (1, TS_2, 4, -4, SRT_PRIMACY_LOWEST),
            ],
            [(1, TS_1, Decimal("0.123")), (1, TS_2, Decimal("0.0004"))],
        ),  # Multiple, some aggregation, finishing on non aggregate value
        (
            [
                (1, TS_1, 4, 4, SRT_PRIMACY_HIGH),
                (1, TS_2, 1, 1, SRT_PRIMACY_HIGH),
                (1, TS_2, 2, 2, SRT_PRIMACY_HIGH),
                (1, TS_2, 3, 3, SRT_PRIMACY_HIGH),
            ],
            [(1, TS_1, Decimal("40000")), (1, TS_2, Decimal("3210"))],
        ),  # Multiple, some aggregation, finishing on aggregate value
        (
            [
                (1, TS_1, 1, 0, SRT_PRIMACY_HIGH),
                (1, TS_1, 2, 0, SRT_PRIMACY_HIGH),
                (1, TS_2, 3, 0, SRT_PRIMACY_HIGH),
                (1, TS_2, 4, 0, SRT_PRIMACY_HIGH),
                (2, TS_1, 5, 0, SRT_PRIMACY_HIGH),
                (2, TS_2, 6, 0, SRT_PRIMACY_HIGH),
                (2, TS_2, 7, 0, SRT_PRIMACY_HIGH),
            ],
            [(1, TS_1, Decimal("3")), (1, TS_2, Decimal("7")), (2, TS_1, Decimal("5")), (2, TS_2, Decimal("13"))],
        ),  # Multiple aggregations
        (
            [
                (1, TS_1, 1, 0, SRT_PRIMACY_HIGH),
                (1, TS_1, 2, 0, SRT_PRIMACY_HIGHEST),
                (1, TS_2, 3, 0, SRT_PRIMACY_LOW),
                (1, TS_2, 4, 0, SRT_PRIMACY_HIGH),
                (2, TS_1, 5, 0, SRT_PRIMACY_LOWEST),
                (2, TS_2, 6, 0, SRT_PRIMACY_LOW),
                (2, TS_2, 7, 0, SRT_PRIMACY_LOW),
            ],
            [(1, TS_1, Decimal("2")), (1, TS_2, Decimal("4")), (2, TS_1, Decimal("5")), (2, TS_2, Decimal("13"))],
        ),  # Multiple aggregations - only best values for each aggregation
    ],
)
def test_aggregate_readings_for_site_timestamp(
    expected_inputs: tuple[int, datetime, int, int, SiteReadingType], expected_outputs: tuple[int, datetime, Decimal]
):
    """Tests aggregate_readings_for_site_timestamp using a shorthand definition for input/output readings

    expected_inputs: (site_id, time_period_start, value_int, pow10, srt)"""
    duration_seconds = 54123

    # Convert our simplified input data into real input site_readings
    input_site_readings: list[SiteReading] = []
    for site_id, time_period_start, value_int, pow10, srt in expected_inputs:
        sr: SiteReading = generate_class_instance(SiteReading, generate_relationships=True)
        cloned_srt: SiteReadingType = clone_class_instance(srt)  # Dont modify the global test variable
        sr.site_reading_type = cloned_srt
        sr.site_reading_type.site_id = site_id
        sr.site_reading_type.power_of_ten_multiplier = pow10
        sr.time_period_seconds = duration_seconds
        sr.time_period_start = time_period_start
        sr.value = value_int

        input_site_readings.append(sr)

    actual = list(BillingMapper.aggregate_readings_for_site_timestamp(input_site_readings))
    assert_list_type(BillingReading, actual, len(expected_outputs))

    # Validate that the returned values aggregate in the expected way
    for tuple_vals, actual_billing_report in zip(expected_outputs, actual):
        site_id, time_period_start, value = tuple_vals
        expected_billing_report = BillingReading(
            site_id=site_id, period_start=time_period_start, duration_seconds=duration_seconds, value=value
        )
        assert_class_instance_equality(BillingReading, expected_billing_report, actual_billing_report)


@pytest.mark.parametrize(
    "optional_is_none",
    [(True), (False)],
)
def test_map_doe(optional_is_none: bool):
    original: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=101, optional_is_none=optional_is_none
    )

    mapped = BillingMapper.map_doe(original)
    assert isinstance(mapped, BillingDoe)
    assert_class_instance_equality(BillingDoe, original, mapped, ignored_properties=set(["period_start"]))
    assert mapped.period_start == original.start_time


@pytest.mark.parametrize(
    "optional_is_none",
    [(True), (False)],
)
def test_map_rate(optional_is_none: bool):
    original: TariffGeneratedRate = generate_class_instance(
        TariffGeneratedRate, seed=101, optional_is_none=optional_is_none
    )

    mapped = BillingMapper.map_rate(original)
    assert isinstance(mapped, BillingTariffRate)
    assert_class_instance_equality(BillingTariffRate, original, mapped, ignored_properties=set(["period_start"]))
    assert mapped.period_start == original.start_time


@pytest.mark.parametrize(
    "optional_is_none",
    [(True), (False)],
)
def test_map_to_aggregator_response(optional_is_none: bool):
    agg: Aggregator = generate_class_instance(Aggregator, seed=101, optional_is_none=optional_is_none)
    period_start = datetime(2023, 4, 5, 6, 7)
    period_end = datetime(2023, 6, 7, 8, 9, tzinfo=timezone.utc)
    tariff_id = 456
    billing_data: BillingData = BillingData(
        varh_readings=[
            generate_class_instance(
                SiteReading, seed=202, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
        wh_readings=[
            generate_class_instance(
                SiteReading, seed=303, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
        active_does=[generate_class_instance(DynamicOperatingEnvelope, seed=404, optional_is_none=optional_is_none)],
        active_tariffs=[generate_class_instance(TariffGeneratedRate, seed=505, optional_is_none=optional_is_none)],
        watt_readings=[
            generate_class_instance(
                SiteReading, seed=606, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
    )

    mapped = BillingMapper.map_to_aggregator_response(agg, tariff_id, period_start, period_end, billing_data)
    assert isinstance(mapped, AggregatorBillingResponse)
    assert mapped.period_start == period_start
    assert mapped.period_end == period_end
    assert mapped.aggregator_name == agg.name
    assert mapped.aggregator_id == agg.aggregator_id
    assert mapped.tariff_id == tariff_id

    assert_list_type(BillingReading, mapped.varh_readings, 1)
    assert_list_type(BillingReading, mapped.wh_readings, 1)
    assert_list_type(BillingReading, mapped.watt_readings, 1)
    assert_list_type(BillingDoe, mapped.active_does, 1)
    assert_list_type(BillingTariffRate, mapped.active_tariffs, 1)

    # This isn't meant to be exhaustive - the other tests will cover that - this will just ensure
    # the wh readings to go the wh list etc.
    assert mapped.varh_readings[0].period_start == billing_data.varh_readings[0].time_period_start
    assert mapped.wh_readings[0].period_start == billing_data.wh_readings[0].time_period_start
    assert mapped.watt_readings[0].period_start == billing_data.watt_readings[0].time_period_start


@pytest.mark.parametrize(
    "optional_is_none",
    [(True), (False)],
)
def test_map_to_sites_response(optional_is_none: bool):
    site_ids = [44, 1, 69]
    period_start = datetime(2023, 4, 5, 6, 7)
    period_end = datetime(2023, 6, 7, 8, 9, tzinfo=timezone.utc)
    tariff_id = 456
    billing_data: BillingData = BillingData(
        varh_readings=[
            generate_class_instance(
                SiteReading, seed=202, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
        wh_readings=[
            generate_class_instance(
                SiteReading, seed=303, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
        active_does=[generate_class_instance(DynamicOperatingEnvelope, seed=404, optional_is_none=optional_is_none)],
        active_tariffs=[generate_class_instance(TariffGeneratedRate, seed=505, optional_is_none=optional_is_none)],
        watt_readings=[
            generate_class_instance(
                SiteReading, seed=606, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
    )

    mapped = BillingMapper.map_to_sites_response(site_ids, tariff_id, period_start, period_end, billing_data)
    assert isinstance(mapped, SiteBillingResponse)
    assert mapped.site_ids == site_ids
    assert mapped.period_start == period_start
    assert mapped.period_end == period_end
    assert mapped.tariff_id == tariff_id
    assert_list_type(BillingReading, mapped.varh_readings, 1)
    assert_list_type(BillingReading, mapped.wh_readings, 1)
    assert_list_type(BillingReading, mapped.watt_readings, 1)
    assert_list_type(BillingDoe, mapped.active_does, 1)
    assert_list_type(BillingTariffRate, mapped.active_tariffs, 1)

    # This isn't meant to be exhaustive - the other tests will cover that - this will just ensure
    # the wh readings to go the wh list etc.
    assert mapped.varh_readings[0].period_start == billing_data.varh_readings[0].time_period_start
    assert mapped.wh_readings[0].period_start == billing_data.wh_readings[0].time_period_start
    assert mapped.watt_readings[0].period_start == billing_data.watt_readings[0].time_period_start


@pytest.mark.parametrize(
    "optional_is_none",
    [(True), (False)],
)
def test_map_to_calculation_log_response(optional_is_none: bool):
    log: CalculationLog = generate_class_instance(CalculationLog, seed=101, optional_is_none=optional_is_none)
    tariff_id = 456
    billing_data: BillingData = BillingData(
        varh_readings=[
            generate_class_instance(
                SiteReading, seed=202, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
        wh_readings=[
            generate_class_instance(
                SiteReading, seed=303, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
        active_does=[generate_class_instance(DynamicOperatingEnvelope, seed=404, optional_is_none=optional_is_none)],
        active_tariffs=[generate_class_instance(TariffGeneratedRate, seed=505, optional_is_none=optional_is_none)],
        watt_readings=[
            generate_class_instance(
                SiteReading, seed=606, optional_is_none=optional_is_none, generate_relationships=True
            )
        ],
    )

    mapped = BillingMapper.map_to_calculation_log_response(log, tariff_id, billing_data)
    assert isinstance(mapped, CalculationLogBillingResponse)
    assert mapped.calculation_log_id == log.calculation_log_id
    assert mapped.tariff_id == tariff_id
    assert_list_type(BillingReading, mapped.varh_readings, 1)
    assert_list_type(BillingReading, mapped.wh_readings, 1)
    assert_list_type(BillingReading, mapped.watt_readings, 1)
    assert_list_type(BillingDoe, mapped.active_does, 1)
    assert_list_type(BillingTariffRate, mapped.active_tariffs, 1)

    # This isn't meant to be exhaustive - the other tests will cover that - this will just ensure
    # the wh readings to go the wh list etc.
    assert mapped.varh_readings[0].period_start == billing_data.varh_readings[0].time_period_start
    assert mapped.wh_readings[0].period_start == billing_data.wh_readings[0].time_period_start
    assert mapped.watt_readings[0].period_start == billing_data.watt_readings[0].time_period_start
