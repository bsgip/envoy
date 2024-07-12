import unittest.mock as mock
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.pricing import TariffProfileResponse, TimeTariffIntervalResponse

from envoy.server.crud.pricing import TariffGeneratedRateDailyStats
from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.sep2.pricing import (
    TOTAL_PRICING_READING_TYPES,
    ConsumptionTariffIntervalMapper,
    PricingReadingType,
    PricingReadingTypeMapper,
    RateComponentMapper,
    TariffProfileMapper,
    TimeTariffIntervalMapper,
)
from envoy.server.model.tariff import PRICE_DECIMAL_PLACES, Tariff, TariffGeneratedRate
from envoy.server.request_state import RequestStateParameters


@pytest.mark.parametrize(
    "enum_val",
    PricingReadingType,
)
def test_create_reading_type(enum_val: PricingReadingType):
    """Just makes sure we don't get any exceptions for the known enum types"""
    rs_params = RequestStateParameters(1, None, None)
    result = PricingReadingTypeMapper.create_reading_type(rs_params, enum_val)
    assert result
    assert result.href
    assert result.flowDirection


@pytest.mark.parametrize(
    "enum_val",
    PricingReadingType,
)
def test_extract_price(enum_val: PricingReadingType):
    """Just makes sure we don't get any exceptions for the known enum types"""
    result = PricingReadingTypeMapper.extract_price(enum_val, generate_class_instance(TariffGeneratedRate))
    assert result


def test_extract_price_unique_values():
    """Just makes sure get unique values for the enum types for the same rate"""
    vals: list[Decimal] = []
    src: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate)
    for e in PricingReadingType:
        vals.append(PricingReadingTypeMapper.extract_price(e, src))
    assert len(vals) == len(set(vals))


@pytest.mark.parametrize(
    "bad_enum_val",
    [None, 9876, -1, "ABC"],
)
def test_create_reading_type_failure(bad_enum_val):
    """Tests that bad enum lookups fail in a predictable way"""

    with pytest.raises(InvalidMappingError):
        PricingReadingTypeMapper.create_reading_type(RequestStateParameters(1, None, None), bad_enum_val)


def test_tariff_profile_nosite_mapping():
    """Non exhaustive test of the tariff profile mapping - mainly to sanity check important fields and ensure
    that exceptions aren't being raised"""
    all_set: Tariff = generate_class_instance(Tariff, seed=101, optional_is_none=False)
    rs_params = RequestStateParameters(1, None, None)
    mapped_all_set = TariffProfileMapper.map_to_nosite_response(rs_params, all_set)
    assert mapped_all_set
    assert mapped_all_set.href
    assert mapped_all_set.pricePowerOfTenMultiplier == -PRICE_DECIMAL_PLACES
    assert mapped_all_set.rateCode == all_set.dnsp_code
    assert mapped_all_set.currency == all_set.currency_code
    assert mapped_all_set.RateComponentListLink
    assert mapped_all_set.RateComponentListLink.href
    assert mapped_all_set.RateComponentListLink.href.startswith(mapped_all_set.href)
    assert (
        mapped_all_set.RateComponentListLink.all_ == 0
    ), "Raw tariff mappings have no rates - need site info to get this information"

    some_set: Tariff = generate_class_instance(Tariff, seed=202, optional_is_none=True)
    mapped_some_set = TariffProfileMapper.map_to_nosite_response(rs_params, some_set)
    assert mapped_some_set
    assert mapped_some_set.href
    assert mapped_some_set.pricePowerOfTenMultiplier == -PRICE_DECIMAL_PLACES
    assert mapped_some_set.rateCode == some_set.dnsp_code
    assert mapped_some_set.currency == some_set.currency_code
    assert mapped_some_set.RateComponentListLink
    assert mapped_some_set.RateComponentListLink.href
    assert mapped_some_set.RateComponentListLink.href.startswith(mapped_some_set.href)
    assert (
        mapped_some_set.RateComponentListLink.all_ == 0
    ), "Raw tariff mappings have no rates - need site info to get this information"


def test_tariff_profile_mapping():
    """Non exhaustive test of the tariff profile mapping - mainly to sanity check important fields and ensure
    that exceptions aren't being raised"""
    site_id = 9876
    total_rates = 76543
    all_set: Tariff = generate_class_instance(Tariff, seed=101, optional_is_none=False)
    rs_params = RequestStateParameters(1, None, None)
    mapped_all_set = TariffProfileMapper.map_to_response(rs_params, all_set, site_id, total_rates)
    assert mapped_all_set
    assert mapped_all_set.href
    assert mapped_all_set.pricePowerOfTenMultiplier == -PRICE_DECIMAL_PLACES, "We send $1 as 10000 * 10^-4"
    assert mapped_all_set.rateCode == all_set.dnsp_code
    assert mapped_all_set.currency == all_set.currency_code
    assert mapped_all_set.RateComponentListLink
    assert mapped_all_set.RateComponentListLink.href
    assert mapped_all_set.RateComponentListLink.href.startswith(mapped_all_set.href)
    assert str(site_id) in mapped_all_set.RateComponentListLink.href
    assert mapped_all_set.RateComponentListLink.all_ == total_rates

    some_set: Tariff = generate_class_instance(Tariff, seed=202, optional_is_none=True)
    mapped_some_set = TariffProfileMapper.map_to_response(rs_params, some_set, site_id, total_rates)
    assert mapped_some_set
    assert mapped_some_set.href
    assert mapped_some_set.pricePowerOfTenMultiplier == -PRICE_DECIMAL_PLACES
    assert mapped_some_set.rateCode == some_set.dnsp_code
    assert mapped_some_set.currency == some_set.currency_code
    assert mapped_some_set.RateComponentListLink
    assert mapped_some_set.RateComponentListLink.href
    assert mapped_some_set.RateComponentListLink.href.startswith(mapped_some_set.href)
    assert str(site_id) in mapped_some_set.RateComponentListLink.href
    assert mapped_some_set.RateComponentListLink.all_ == total_rates


def test_tariff_profile_list_nosite_mapping():
    """Non exhaustive test of the tariff profile list mapping - mainly to sanity check important fields and ensure
    that exceptions aren't being raised"""
    tariffs: list[Tariff] = [
        generate_class_instance(Tariff, seed=101, optional_is_none=False),
        generate_class_instance(Tariff, seed=202, optional_is_none=True),
    ]
    count = 123
    rs_params = RequestStateParameters(1, None, None)

    mapped_all_set = TariffProfileMapper.map_to_list_nosite_response(rs_params, tariffs, count)
    assert mapped_all_set
    assert mapped_all_set.all_ == count
    assert mapped_all_set.results == 2
    assert len(mapped_all_set.TariffProfile) == 2
    assert all([isinstance(tp, TariffProfileResponse) for tp in mapped_all_set.TariffProfile])


def test_tariff_profile_list_mapping():
    """Non exhaustive test of the tariff profile list mapping - mainly to sanity check important fields and ensure
    that exceptions aren't being raised"""
    tariffs: list[Tariff] = [
        generate_class_instance(Tariff, seed=101, optional_is_none=False),
        generate_class_instance(Tariff, seed=202, optional_is_none=True),
    ]
    tariff_rate_counts = [456, 789]
    tariff_count = 123
    site_id = 112234
    rs_params = RequestStateParameters(1, None, None)

    mapped_all_set = TariffProfileMapper.map_to_list_response(
        rs_params, zip(tariffs, tariff_rate_counts), tariff_count, site_id
    )
    assert mapped_all_set
    assert mapped_all_set.all_ == tariff_count
    assert mapped_all_set.results == 2
    assert len(mapped_all_set.TariffProfile) == 2
    assert all([isinstance(tp, TariffProfileResponse) for tp in mapped_all_set.TariffProfile])
    assert all([str(site_id) in tp.href for tp in mapped_all_set.TariffProfile])
    assert all([str(site_id) in tp.RateComponentListLink.href for tp in mapped_all_set.TariffProfile])

    # Double check our rate component counts get handed down to the child lists correctly
    assert mapped_all_set.TariffProfile[0].RateComponentListLink.all_ == tariff_rate_counts[0]
    assert mapped_all_set.TariffProfile[1].RateComponentListLink.all_ == tariff_rate_counts[1]


@mock.patch("envoy.server.mapper.sep2.pricing.PricingReadingTypeMapper")
def test_rate_component_mapping(mock_PricingReadingTypeMapper: mock.MagicMock):
    """Non exhaustive test of rate component mapping - mainly to weed out obvious
    validation errors"""
    total_rates: int = 123
    tariff_id: int = 456
    site_id: int = 789
    pricing_reading: PricingReadingType = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    day: date = date(2014, 1, 25)
    rs_params = RequestStateParameters(1, None, None)

    pricing_reading_type_href = "/abc/213"
    mock_PricingReadingTypeMapper.pricing_reading_type_href = mock.Mock(return_value=pricing_reading_type_href)

    result = RateComponentMapper.map_to_response(rs_params, total_rates, tariff_id, site_id, pricing_reading, day)
    assert result
    assert result.ReadingTypeLink
    assert result.ReadingTypeLink.href == pricing_reading_type_href
    assert result.mRID
    assert result.href
    assert result.TimeTariffIntervalListLink
    assert result.TimeTariffIntervalListLink.href
    assert result.TimeTariffIntervalListLink.href.startswith(result.href)

    mock_PricingReadingTypeMapper.pricing_reading_type_href.assert_called_once_with(rs_params, pricing_reading)


@pytest.mark.parametrize(
    "rates",
    # These expected values are based on PRICE_DECIMAL_PLACES
    [
        # Basic test case of get everything
        (
            ([(date(2022, 1, 1), 5), (date(2022, 1, 2), 4)], 0, 0),  # Input
            (date(2022, 1, 1), 5, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2022, 1, 2), 4, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
        ),
        # Skip start
        (
            ([(date(2022, 1, 1), 5), (date(2022, 1, 2), 4)], 2, 0),  # Input
            (date(2022, 1, 1), 5, PricingReadingType.IMPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2022, 1, 2), 4, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
        ),
        # Skip end
        (
            ([(date(2022, 1, 1), 5), (date(2022, 1, 2), 4)], 0, 2),  # Input
            (date(2022, 1, 1), 5, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2022, 1, 2), 4, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # Last output child RateComponent
        ),
        # Skip both
        (
            ([(date(2022, 1, 1), 5), (date(2022, 1, 2), 4)], 1, 2),  # Input
            (date(2022, 1, 1), 5, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2022, 1, 2), 4, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # Last output child RateComponent
        ),
        # Big skip past entire dates
        (
            ([(date(2022, 1, 1), 5), (date(2022, 1, 2), 4), (date(2022, 1, 3), 3)], 5, 5),  # Input
            (date(2022, 1, 2), 4, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2022, 1, 2), 4, PricingReadingType.IMPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
        ),
        # Singleton
        (
            ([(date(2022, 1, 1), 5)], 1, 2),  # Input
            (date(2022, 1, 1), 5, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2022, 1, 1), 5, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # Last output child RateComponent
        ),
    ],
)
def test_rate_component_list_mapping_paging(rates):
    """Tests the somewhat unique paging implementation that sees the client seeing 12 rates but in reality
    there are only 3 under the hood. The test isn't exhaustive - it mainly checks that the
    mapping properly trims entries from the start/end of the list"""
    (
        (input_date_counts, skip_start, skip_end),
        (first_date, first_count, first_price_type),
        (last_date, last_count, last_price_type),
    ) = rates

    stats = TariffGeneratedRateDailyStats(total_distinct_dates=9876, single_date_counts=input_date_counts)
    expected_count = (len(input_date_counts) * TOTAL_PRICING_READING_TYPES) - skip_end - skip_start
    rs_params = RequestStateParameters(1, None, None)

    list_response = RateComponentMapper.map_to_list_response(rs_params, stats, skip_start, skip_end, 1, 1)

    # check the overall structure of the list
    assert list_response.all_ == 9876 * TOTAL_PRICING_READING_TYPES
    assert list_response.results == len(list_response.RateComponent)
    assert len(list_response.RateComponent) == expected_count

    # validate the first / last RateComponents
    if expected_count > 0:
        first = list_response.RateComponent[0]
        assert first.href.endswith(f"/{first_price_type}"), f"{first.href} should end with /{first_price_type}"
        assert f"/{first_date.isoformat()}/" in first.href
        assert first.TimeTariffIntervalListLink.all_ == first_count

        last = list_response.RateComponent[-1]
        assert last.href.endswith(f"/{last_price_type}"), f"{last.href} should end with /{last_price_type}"
        assert f"/{last_date.isoformat()}/" in last.href
        assert last.TimeTariffIntervalListLink.all_ == last_count


@pytest.mark.parametrize(
    "input_price, expected_price",
    # These expected values are based on PRICE_DECIMAL_PLACES
    [
        (Decimal("1.2345"), 12345),
        (Decimal("1"), 10000),
        (Decimal("0"), 0),
        (Decimal("1.999999"), 19999),
        (Decimal("-12.3456789"), -123456),
    ],
)
def test_consumption_tariff_interval_mapping_prices(input_price: Decimal, expected_price: int):
    """Checks PRICE_DECIMAL_POWER is used to calculate sep2 integer price values"""
    tariff_id: int = 1
    site_id: int = 2
    pricing_reading: PricingReadingType = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    day: date = date(2015, 9, 23)
    time_of_day: time = time(9, 40)
    rs_params = RequestStateParameters(1, None, None)

    mapped = ConsumptionTariffIntervalMapper.map_to_response(
        rs_params, tariff_id, site_id, pricing_reading, day, time_of_day, input_price
    )
    assert mapped.price == expected_price
    assert mapped.href
    assert str(expected_price) in mapped.href

    mapped_list = ConsumptionTariffIntervalMapper.map_to_list_response(
        rs_params, tariff_id, site_id, pricing_reading, day, time_of_day, input_price
    )
    assert str(expected_price) in mapped_list.href
    assert mapped_list.ConsumptionTariffInterval
    assert len(mapped_list.ConsumptionTariffInterval) == 1
    child = mapped_list.ConsumptionTariffInterval[0]
    assert str(expected_price) in child.href
    assert child.href != mapped_list.href


@mock.patch("envoy.server.mapper.sep2.pricing.ConsumptionTariffIntervalMapper")
@mock.patch("envoy.server.mapper.sep2.pricing.PricingReadingTypeMapper")
def test_time_tariff_interval_mapping(
    mock_PricingReadingTypeMapper: mock.MagicMock, mock_ConsumptionTariffIntervalMapper: mock.MagicMock
):
    """Non exhaustive test on TimeTariffInterval mapping - mainly to catch any validation issues"""
    rate_all_set: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate, seed=101, optional_is_none=False)
    rt = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    cti_list_href = "abc/123"
    extracted_price = Decimal("543.211")
    rs_params = RequestStateParameters(1, None, None)

    mock_PricingReadingTypeMapper.extract_price = mock.Mock(return_value=extracted_price)
    mock_ConsumptionTariffIntervalMapper.list_href = mock.Mock(return_value=cti_list_href)

    # Cursory check on values
    mapped_all_set = TimeTariffIntervalMapper.map_to_response(rs_params, rate_all_set, rt)
    assert mapped_all_set
    assert mapped_all_set.href
    assert mapped_all_set.ConsumptionTariffIntervalListLink.href == cti_list_href

    # Assert we are utilising the inbuilt utils
    mock_PricingReadingTypeMapper.extract_price.assert_called_once_with(rt, rate_all_set)
    mock_ConsumptionTariffIntervalMapper.list_href.assert_called_once_with(
        rs_params,
        rate_all_set.tariff_id,
        rate_all_set.site_id,
        rt,
        rate_all_set.start_time.date(),
        rate_all_set.start_time.time(),
        extracted_price,
    )


@mock.patch("envoy.server.mapper.sep2.pricing.ConsumptionTariffIntervalMapper")
@mock.patch("envoy.server.mapper.sep2.pricing.PricingReadingTypeMapper")
def test_time_tariff_interval_list_mapping(
    mock_PricingReadingTypeMapper: mock.MagicMock, mock_ConsumptionTariffIntervalMapper: mock.MagicMock
):
    """Non exhaustive test on TimeTariffIntervalList mapping - mainly to catch any validation issues"""
    rates: list[TariffGeneratedRate] = [
        generate_class_instance(TariffGeneratedRate, seed=101, optional_is_none=False),
        generate_class_instance(TariffGeneratedRate, seed=202, optional_is_none=True),
    ]
    rt = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    cti_list_href = "abc/123"
    extracted_price = Decimal("-543.211")
    total = 632
    mock_PricingReadingTypeMapper.extract_price = mock.Mock(return_value=extracted_price)
    mock_ConsumptionTariffIntervalMapper.list_href = mock.Mock(return_value=cti_list_href)
    rs_params = RequestStateParameters(1, None, None)

    mapped = TimeTariffIntervalMapper.map_to_list_response(rs_params, rates, rt, total)
    assert mapped.all_ == total
    assert mapped.results == len(rates)
    assert len(mapped.TimeTariffInterval) == len(rates)
    assert all(
        [isinstance(x, TimeTariffIntervalResponse) for x in mapped.TimeTariffInterval]
    ), "Checking all list items are the correct type"
    list_items_mrids = [x.mRID for x in mapped.TimeTariffInterval]
    assert len(list_items_mrids) == len(set(list_items_mrids)), "Checking all list items are unique"

    # cursory check that we mapped each rate into the response
    assert mock_PricingReadingTypeMapper.extract_price.call_count == len(rates)
    assert mock_ConsumptionTariffIntervalMapper.list_href.call_count == len(rates)


def test_mrid_uniqueness():
    """Test our mrid's for the mapped entities differ from each other despite sharing database ids"""
    id = 1
    reading_type = PricingReadingType(id)
    day = datetime.fromtimestamp(id).date()

    tariff: Tariff = generate_class_instance(Tariff)
    rate: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate)
    tariff.tariff_id = id
    rs_params = RequestStateParameters(1, None, None)

    rate.tariff_generated_rate_id = id
    rate.tariff_id = id
    rate.site_id = id

    tti = TimeTariffIntervalMapper.map_to_response(rs_params, rate, reading_type)
    rc = RateComponentMapper.map_to_response(rs_params, 999, id, id, reading_type, day)
    tp = TariffProfileMapper.map_to_response(rs_params, tariff, id, 999)

    assert tti.mRID != rc.mRID
    assert tti.mRID != tp.mRID
    assert rc.mRID != tp.mRID
