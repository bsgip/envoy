import unittest.mock as mock
from datetime import date, datetime, time
from typing import Union
from urllib.parse import quote

import pytest

from envoy.server.manager.pricing import (
    ConsumptionTariffIntervalManager,
    RateComponentManager,
    TimeTariffIntervalManager,
)
from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.model.site import Site
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.schema.sep2.metering import ConsumptionBlockType
from envoy.server.schema.sep2.pricing import TimeTariffIntervalListResponse, TimeTariffIntervalResponse
from tests.data.fake.generator import generate_class_instance


@pytest.mark.parametrize(
    "expected_result",
    [
        ('2022-11-10', date(2022, 11, 10)),
        ('2036-09-30', date(2036, 9, 30)),
        ('1985-01-02', date(1985, 1, 2)),
        ('2020-02-29', date(2020, 2, 29)),

        ('', InvalidMappingError),
        ('2022', InvalidMappingError),
        ('2022/10/09', InvalidMappingError),
        ('2022-11-31', InvalidMappingError),  # There is no 31st Nov
        ('2021-02-29', InvalidMappingError),  # Not a leap year
        ('2022-Nov-02', InvalidMappingError),
     ],
)
def test_parse_rate_component_id(expected_result: tuple[str, Union[time, type]]):
    """Simple test on parser generating valid values / catching errors"""
    (input, output) = expected_result

    if isinstance(output, date):
        assert RateComponentManager.parse_rate_component_id(input) == output
    else:
        with pytest.raises(output):
            RateComponentManager.parse_rate_component_id(input) == output


@pytest.mark.parametrize(
    "expected_result",
    [
        ('11:59', time(11, 59)),
        ('13:01', time(13, 1)),
        ('02:34', time(2, 34)),
        ('00:00', time(0, 0)),
        ('23:59', time(23, 59)),

        ('', InvalidMappingError),
        ('12:3', InvalidMappingError),
        ('12:60', InvalidMappingError),
        ('24:01', InvalidMappingError),
        ('11-12', InvalidMappingError),
        ('11 12', InvalidMappingError),
        (' 12:13 ', InvalidMappingError),
     ],
)
def test_parse_time_tariff_interval_id(expected_result: tuple[str, Union[time, type]]):
    """Simple test on parser generating valid values / catching errors"""

    (input, output) = expected_result

    if isinstance(output, time):
        assert TimeTariffIntervalManager.parse_time_tariff_interval_id(input) == output
    else:
        with pytest.raises(output):
            TimeTariffIntervalManager.parse_time_tariff_interval_id(input) == output


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_single_site_with_site_id")
async def test_fetch_consumption_tariff_interval_list(mock_select_single_site_with_site_id: mock.MagicMock,
                                                      mock_RateComponentManager: mock.MagicMock,
                                                      mock_TimeTariffIntervalManager: mock.MagicMock):
    tariff_id = 54321
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = '2022-02-01'
    time_tariff_interval = '13:37'
    price = 12345
    mock_session = mock.Mock()
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=date(2022, 1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=time(1, 2))
    mock_select_single_site_with_site_id.return_value = generate_class_instance(Site)

    result = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval_list(mock_session, aggregator_id, tariff_id, site_id, rate_component_id, time_tariff_interval, price)
    assert result.all_ == 1
    assert len(result.ConsumptionTariffInterval) == 1
    cti = result.ConsumptionTariffInterval[0]
    assert cti.consumptionBlock == ConsumptionBlockType.NOT_APPLICABLE
    assert cti.price == price

    # check that the href looks roughly okayish
    assert quote(time_tariff_interval) in cti.href
    assert quote(rate_component_id) in cti.href
    assert str(tariff_id) in cti.href
    assert str(price) in cti.href

    # check we validated the ids
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id=site_id, aggregator_id=aggregator_id)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_single_site_with_site_id")
async def test_fetch_consumption_tariff_interval(mock_select_single_site_with_site_id: mock.MagicMock,
                                                 mock_RateComponentManager: mock.MagicMock,
                                                 mock_TimeTariffIntervalManager: mock.MagicMock):
    tariff_id = 665544
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = '2023-02-01'
    time_tariff_interval = '09:08'
    price = -1456
    mock_session = mock.Mock()
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=date(2022, 1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=time(1, 2))
    mock_select_single_site_with_site_id.return_value = generate_class_instance(Site)

    cti = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval(mock_session,
                                                                                   aggregator_id,
                                                                                   tariff_id,
                                                                                   site_id,
                                                                                   rate_component_id,
                                                                                   time_tariff_interval,
                                                                                   price)
    assert cti.consumptionBlock == ConsumptionBlockType.NOT_APPLICABLE
    assert cti.price == price

    # check that the href looks roughly okayish
    assert quote(time_tariff_interval) in cti.href
    assert quote(rate_component_id) in cti.href
    assert str(tariff_id) in cti.href
    assert str(price) in cti.href

    # check we validated the ids
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id=site_id, aggregator_id=aggregator_id)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalMapper")
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_tariff_rate_for_day_time")
async def test_fetch_time_tariff_interval_existing(mock_select_tariff_rate_for_day_time: mock.MagicMock,
                                                   mock_RateComponentManager: mock.MagicMock,
                                                   mock_TimeTariffIntervalManager: mock.MagicMock,
                                                   mock_TimeTariffIntervalMapper: mock.MagicMock):
    """Tests the manager correctly interacts with dependencies"""
    tariff_id = 665544
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = '2023-02-01'
    time_tariff_interval = '09:08'
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    existing_rate: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate)
    mapped_interval: TimeTariffIntervalResponse = generate_class_instance(TimeTariffIntervalResponse)
    mock_session = mock.Mock()
    parsed_date = date(2022, 1, 2)
    parsed_time = time(3, 4)

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=parsed_time)
    mock_select_tariff_rate_for_day_time.return_value = existing_rate
    mock_TimeTariffIntervalMapper.map_to_response.return_value = mapped_interval

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval(mock_session, aggregator_id, tariff_id, site_id,
                                                                        rate_component_id, time_tariff_interval,
                                                                        pricing_type)

    # Assert
    assert result is mapped_interval
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_tariff_rate_for_day_time.assert_called_once_with(mock_session,
                                                                 aggregator_id,
                                                                 tariff_id,
                                                                 site_id,
                                                                 parsed_date,
                                                                 parsed_time)
    mock_TimeTariffIntervalMapper.map_to_response.assert_called_once_with(existing_rate, pricing_type)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_tariff_rate_for_day_time")
async def test_fetch_time_tariff_interval_missing(mock_select_tariff_rate_for_day_time: mock.MagicMock,
                                                  mock_RateComponentManager: mock.MagicMock,
                                                  mock_TimeTariffIntervalManager: mock.MagicMock):
    """Tests the manager correctly interacts with dependencies when there is no rate"""
    tariff_id = 665544
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = '2023-02-01'
    time_tariff_interval = '09:08'
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    mock_session = mock.Mock()
    parsed_date = date(2022, 1, 2)
    parsed_time = time(3, 4)

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=parsed_time)
    mock_select_tariff_rate_for_day_time.return_value = None

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval(mock_session, aggregator_id, tariff_id, site_id,
                                                                        rate_component_id, time_tariff_interval,
                                                                        pricing_type)

    # Assert
    assert result is None
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_tariff_rate_for_day_time.assert_called_once_with(mock_session,
                                                                 aggregator_id,
                                                                 tariff_id,
                                                                 site_id,
                                                                 parsed_date,
                                                                 parsed_time)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalMapper")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_tariff_rates_for_day")
@mock.patch("envoy.server.manager.pricing.count_tariff_rates_for_day")
async def test_fetch_time_tariff_interval_list(mock_count_tariff_rates_for_day: mock.MagicMock,
                                               mock_select_tariff_rates_for_day: mock.MagicMock,
                                               mock_RateComponentManager: mock.MagicMock,
                                               mock_TimeTariffIntervalMapper: mock.MagicMock):
    """Tests the manager correctly interacts with dependencies"""
    tariff_id = 665544
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = '2023-02-01'
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    existing_rates: list[TariffGeneratedRate] = [generate_class_instance(TariffGeneratedRate)]
    mapped_list_response: TimeTariffIntervalListResponse = generate_class_instance(TimeTariffIntervalListResponse)
    total_rate_count = 542
    mock_session = mock.Mock()
    parsed_date = date(2022, 1, 2)
    start = 2
    after = datetime(2023, 1, 2, 3, 4)
    limit = 5

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_select_tariff_rates_for_day.return_value = existing_rates
    mock_count_tariff_rates_for_day.return_value = total_rate_count
    mock_TimeTariffIntervalMapper.map_to_list_response.return_value = mapped_list_response

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval_list(mock_session, aggregator_id, tariff_id,
                                                                             site_id, rate_component_id, pricing_type,
                                                                             start, after, limit)

    # Assert
    assert result is mapped_list_response
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_select_tariff_rates_for_day.assert_called_once_with(mock_session,
                                                             aggregator_id,
                                                             tariff_id,
                                                             site_id,
                                                             parsed_date,
                                                             start,
                                                             after,
                                                             limit)
    mock_count_tariff_rates_for_day.assert_called_once_with(mock_session, aggregator_id, tariff_id, site_id, parsed_date, after)
    mock_TimeTariffIntervalMapper.map_to_list_response.assert_called_once_with(existing_rates, pricing_type,
                                                                               total_rate_count)
