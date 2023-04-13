import unittest.mock as mock
from datetime import date, time
from urllib.parse import quote

import pytest

from envoy.server.manager.pricing import (
    ConsumptionTariffIntervalManager,
    RateComponentManager,
    TimeTariffIntervalManager,
)
from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.schema.sep2.metering import ConsumptionBlockType


def test_parse_rate_component_id():
    """Simple test on parser generating valid values / catching errors"""
    assert RateComponentManager.parse_rate_component_id('2022-11-10') == date(2022, 11, 10)
    assert RateComponentManager.parse_rate_component_id('2036-09-30') == date(2036, 9, 30)
    assert RateComponentManager.parse_rate_component_id('1985-01-02') == date(1985, 1, 2)
    assert RateComponentManager.parse_rate_component_id('2020-02-29') == date(2020, 2, 29)

    with pytest.raises(InvalidMappingError):
        RateComponentManager.parse_rate_component_id('')
    with pytest.raises(InvalidMappingError):
        RateComponentManager.parse_rate_component_id('2022')
    with pytest.raises(InvalidMappingError):
        RateComponentManager.parse_rate_component_id('2022/10/09')
    with pytest.raises(InvalidMappingError):
        RateComponentManager.parse_rate_component_id('2022-11-31')  # There is no 31st Nov
    with pytest.raises(InvalidMappingError):
        RateComponentManager.parse_rate_component_id('2021-02-29')  # Not leap year
    with pytest.raises(InvalidMappingError):
        RateComponentManager.parse_rate_component_id('2022-Nov-02')


def test_parse_time_tariff_interval_id():
    """Simple test on parser generating valid values / catching errors"""
    assert TimeTariffIntervalManager.parse_time_tariff_interval_id('11:59') == time(11, 59)
    assert TimeTariffIntervalManager.parse_time_tariff_interval_id('13:01') == time(13, 1)
    assert TimeTariffIntervalManager.parse_time_tariff_interval_id('02:34') == time(2, 34)
    assert TimeTariffIntervalManager.parse_time_tariff_interval_id('00:00') == time(0, 0)
    assert TimeTariffIntervalManager.parse_time_tariff_interval_id('23:59') == time(23, 59)

    with pytest.raises(InvalidMappingError):
        TimeTariffIntervalManager.parse_time_tariff_interval_id('')
    with pytest.raises(InvalidMappingError):
        TimeTariffIntervalManager.parse_time_tariff_interval_id('12:3')
    with pytest.raises(InvalidMappingError):
        TimeTariffIntervalManager.parse_time_tariff_interval_id('12:60')
    with pytest.raises(InvalidMappingError):
        TimeTariffIntervalManager.parse_time_tariff_interval_id('24:01')
    with pytest.raises(InvalidMappingError):
        TimeTariffIntervalManager.parse_time_tariff_interval_id('11-12')


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
async def test_fetch_consumption_tariff_interval_list(mock_RateComponentManager: mock.MagicMock,
                                                      mock_TimeTariffIntervalManager: mock.MagicMock):
    tariff_id = 54321
    rate_component_id = '2022-02-01'
    time_tariff_interval = '13:37'
    price = 12345
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=time(1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=date(2022, 1, 2))

    result = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval_list(tariff_id, rate_component_id, time_tariff_interval, price)
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


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
async def test_fetch_consumption_tariff_interval(mock_RateComponentManager: mock.MagicMock,
                                                 mock_TimeTariffIntervalManager: mock.MagicMock):
    tariff_id = 665544
    rate_component_id = '2023-02-01'
    time_tariff_interval = '09:08'
    price = -1456
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=time(1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=date(2022, 1, 2))

    cti = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval(tariff_id, rate_component_id, time_tariff_interval, price)
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