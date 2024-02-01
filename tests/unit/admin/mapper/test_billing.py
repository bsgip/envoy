from datetime import datetime, timezone
from decimal import Decimal

import pytest
from envoy_schema.admin.schema.billing import BillingDoe, BillingReading, BillingResponse, BillingTariffRate

from envoy.admin.crud.billing import BillingData
from envoy.admin.mapper.billing import BillingMapper
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.tariff import TariffGeneratedRate
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


@pytest.mark.parametrize(
    "value, power_of_ten, expected_value",
    [
        (1234, 3, Decimal("1.234")),
        (1234, 0, Decimal("1234")),
        (1234, -3, Decimal("1234000")),
        (0, 0, Decimal("0")),
        (0, 10, Decimal("0")),
        (0, -10, Decimal("0")),
    ],
)
def test_map_reading_value_power_of_ten(value: int, power_of_ten: int, expected_value: Decimal):
    """Validates that power of ten is correctly applied when setting value"""
    reading: SiteReading = generate_class_instance(SiteReading, generate_relationships=True)
    reading.value = value
    reading.site_reading_type.power_of_ten_multiplier = power_of_ten

    mapped = BillingMapper.map_reading(reading)

    assert isinstance(mapped, BillingReading)
    assert mapped.value == expected_value
    assert mapped.site_id == reading.site_reading_type.site_id
    assert mapped.period_start == reading.time_period_start
    assert mapped.duration_seconds == reading.time_period_seconds


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
def test_map_to_response(optional_is_none: bool):
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
    )

    mapped = BillingMapper.map_to_response(agg, tariff_id, period_start, period_end, billing_data)
    assert isinstance(mapped, BillingResponse)
    assert len(mapped.varh_readings) == 1
    assert len(mapped.wh_readings) == 1
    assert len(mapped.active_does) == 1
    assert len(mapped.active_tariffs) == 1

    # This isn't meant to be exhaustive - the other tests will cover that - this will just ensure
    # the wh readings to go the wh list.
    assert mapped.varh_readings[0].period_start == billing_data.varh_readings[0].time_period_start
    assert mapped.wh_readings[0].period_start == billing_data.wh_readings[0].time_period_start
