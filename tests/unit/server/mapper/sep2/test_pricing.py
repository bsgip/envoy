
import unittest.mock as mock
from datetime import date, time
from decimal import Decimal

import pytest

from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.mapper.sep2.pricing import (
    ConsumptionTariffIntervalMapper,
    PricingReadingType,
    PricingReadingTypeMapper,
    RateComponentMapper,
    TariffProfileMapper,
    TimeTariffIntervalMapper,
)
from envoy.server.model.tariff import PRICE_DECIMAL_PLACES, Tariff, TariffGeneratedRate
from envoy.server.schema.sep2.pricing import CurrencyCode, TimeTariffIntervalResponse
from tests.data.fake.generator import generate_class_instance


@pytest.mark.parametrize(
    "enum_val",
    PricingReadingType,
)
def test_create_reading_type(enum_val: PricingReadingType):
    """Just makes sure we don't get any exceptions for the known enum types"""
    result = PricingReadingTypeMapper.create_reading_type(enum_val)
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
    [None,
     9876,
     -1,
     'ABC'],
)
def test_create_reading_type_failure(bad_enum_val):
    """Tests that bad enum lookups fail in a predictable way"""
    with pytest.raises(InvalidMappingError):
        PricingReadingTypeMapper.create_reading_type(bad_enum_val)


def test_tariff_profile_mapping():
    """Non exhaustive test of the tariff profile mapping - mainly to sanity check important fields and ensure
    that exceptions arent being raised"""
    all_set: Tariff = generate_class_instance(Tariff, seed=101, optional_is_none=False)
    all_set.currency_code = CurrencyCode.AUSTRALIAN_DOLLAR
    mapped_all_set = TariffProfileMapper.map_to_response(all_set)
    assert mapped_all_set
    assert mapped_all_set.href
    assert mapped_all_set.pricePowerOfTenMultiplier == PRICE_DECIMAL_PLACES
    assert mapped_all_set.rateCode == all_set.dnsp_code
    assert mapped_all_set.currency == all_set.currency_code
    assert mapped_all_set.RateComponentListLink
    assert mapped_all_set.RateComponentListLink.href
    assert mapped_all_set.RateComponentListLink.href.startswith(mapped_all_set.href)
    assert mapped_all_set.RateComponentListLink.all_ == 0, "Raw tariff mappings have no rates - need site info to get this information"

    some_set: Tariff = generate_class_instance(Tariff, seed=202, optional_is_none=True)
    some_set.currency_code = CurrencyCode.US_DOLLAR
    mapped_some_set = TariffProfileMapper.map_to_response(some_set)
    assert mapped_some_set
    assert mapped_some_set.href
    assert mapped_some_set.pricePowerOfTenMultiplier == PRICE_DECIMAL_PLACES
    assert mapped_some_set.rateCode == some_set.dnsp_code
    assert mapped_some_set.currency == some_set.currency_code
    assert mapped_some_set.RateComponentListLink
    assert mapped_some_set.RateComponentListLink.href
    assert mapped_some_set.RateComponentListLink.href.startswith(mapped_some_set.href)
    assert mapped_some_set.RateComponentListLink.all_ == 0, "Raw tariff mappings have no rates - need site info to get this information"


@mock.patch('envoy.server.mapper.sep2.pricing.PricingReadingTypeMapper')
def test_rate_component_mapping(mock_PricingReadingTypeMapper: mock.MagicMock):
    """Non exhaustive test of rate component mapping - mainly to weed out obvious
    validation errors"""
    total_rates: int = 123
    tariff_id: int = 456
    site_id: int = 789
    pricing_reading: PricingReadingType = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    day: date = date(2014, 1, 25)

    pricing_reading_type_href = '/abc/213'
    mock_PricingReadingTypeMapper.pricing_reading_type_href = mock.Mock(return_value=pricing_reading_type_href)

    result = RateComponentMapper.map_to_response(total_rates, tariff_id, site_id, pricing_reading, day)
    assert result
    assert result.ReadingTypeLink
    assert result.ReadingTypeLink.href == pricing_reading_type_href
    assert result.mRID
    assert result.href
    assert result.TimeTariffIntervalListLink
    assert result.TimeTariffIntervalListLink.href
    assert result.TimeTariffIntervalListLink.href.startswith(result.href)

    mock_PricingReadingTypeMapper.pricing_reading_type_href.assert_called_once_with(pricing_reading)


@pytest.mark.parametrize(
    "prices",
    # These expected values are based on PRICE_DECIMAL_PLACES
    [(Decimal("1.2345"), 12345),
     (Decimal("1"), 10000),
     (Decimal("0"), 0),
     (Decimal("1.999999"), 19999),
     (Decimal("-12.3456789"), -123456),
     ],
)
def test_consumption_tariff_interval_mapping_prices(prices: tuple[Decimal, int]):
    """Checks PRICE_DECIMAL_POWER is used to calculate sep2 integer price values"""
    tariff_id: int = 1
    site_id: int = 2
    pricing_reading: PricingReadingType = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    day: date = date(2015, 9, 23)
    time_of_day: time = time(9, 40)

    (input_price, expected_price) = prices

    mapped = ConsumptionTariffIntervalMapper.map_to_response(tariff_id, site_id, pricing_reading, day, time_of_day, input_price)
    assert mapped.price == expected_price
    assert mapped.href


@mock.patch('envoy.server.mapper.sep2.pricing.ConsumptionTariffIntervalMapper')
@mock.patch('envoy.server.mapper.sep2.pricing.PricingReadingTypeMapper')
def test_time_tariff_interval_mapping(mock_PricingReadingTypeMapper: mock.MagicMock,
                                      mock_ConsumptionTariffIntervalMapper: mock.MagicMock):
    """Non exhaustive test on TimeTariffInterval mapping - mainly to catch any validation issues"""
    rate_all_set: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate, seed=101, optional_is_none=False)
    rt = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    cti_list_href = 'abc/123'
    extracted_price = Decimal('543.211')

    mock_PricingReadingTypeMapper.extract_price = mock.Mock(return_value=extracted_price)
    mock_ConsumptionTariffIntervalMapper.list_href = mock.Mock(return_value=cti_list_href)

    # Cursory check on values
    mapped_all_set = TimeTariffIntervalMapper.map_to_response(rate_all_set, rt)
    assert mapped_all_set
    assert mapped_all_set.href
    assert mapped_all_set.ConsumptionTariffIntervalListLink.href == cti_list_href

    # Assert we are utilising the inbuilt utils
    mock_PricingReadingTypeMapper.extract_price.assert_called_once_with(rt, rate_all_set)
    mock_ConsumptionTariffIntervalMapper.list_href.assert_called_once_with(
        rate_all_set.tariff_id,
        rate_all_set.site_id,
        rt,
        rate_all_set.start_time.date(),
        rate_all_set.start_time.time(),
        extracted_price
    )


@mock.patch('envoy.server.mapper.sep2.pricing.ConsumptionTariffIntervalMapper')
@mock.patch('envoy.server.mapper.sep2.pricing.PricingReadingTypeMapper')
def test_time_tariff_interval_list_mapping(mock_PricingReadingTypeMapper: mock.MagicMock,
                                           mock_ConsumptionTariffIntervalMapper: mock.MagicMock):
    """Non exhaustive test on TimeTariffIntervalList mapping - mainly to catch any validation issues"""
    rates: list[TariffGeneratedRate] = [
        generate_class_instance(TariffGeneratedRate, seed=101, optional_is_none=False),
        generate_class_instance(TariffGeneratedRate, seed=202, optional_is_none=True),
    ]
    rt = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    cti_list_href = 'abc/123'
    extracted_price = Decimal('-543.211')
    total = 632
    mock_PricingReadingTypeMapper.extract_price = mock.Mock(return_value=extracted_price)
    mock_ConsumptionTariffIntervalMapper.list_href = mock.Mock(return_value=cti_list_href)

    mapped = TimeTariffIntervalMapper.map_to_list_response(rates, rt, total)
    assert mapped.all_ == total
    assert mapped.results == len(rates)
    assert len(mapped.TimeTariffInterval) == len(rates)
    assert all([type(x) == TimeTariffIntervalResponse for x in mapped.TimeTariffInterval]), "Checking all list items are the correct type"
    list_items_mrids = [x.mRID for x in mapped.TimeTariffInterval]
    assert len(list_items_mrids) == len(set(list_items_mrids)), "Checking all list items are unique"

    # cursory check that we mapped each rate into the response
    assert mock_PricingReadingTypeMapper.extract_price.call_count == len(rates)
    assert mock_ConsumptionTariffIntervalMapper.list_href.call_count == len(rates)
