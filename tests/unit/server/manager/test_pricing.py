from urllib.parse import quote

import pytest

from envoy.server.manager.pricing import ConsumptionTariffIntervalManager
from envoy.server.schema.sep2.metering import ConsumptionBlockType


@pytest.mark.anyio
async def test_fetch_consumption_tariff_interval_list():
    tariff_id = 54321
    rate_component_id = '2022-02-01'
    time_tariff_interval = '13:37'
    price = 12345

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
