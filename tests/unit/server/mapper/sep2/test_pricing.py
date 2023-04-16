
import unittest.mock as mock
from datetime import date

import pytest

from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.mapper.sep2.pricing import (
    PricingReadingType,
    PricingReadingTypeMapper,
    RateComponentMapper,
    TariffProfileMapper,
)
from envoy.server.model.tariff import Tariff
from envoy.server.schema.sep2.pricing import CurrencyCode
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
