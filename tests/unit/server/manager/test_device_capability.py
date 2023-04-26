import unittest.mock as mock

import pytest

from envoy.server.manager.device_capability import DeviceCapabilityManager
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
async def test_device_capability_manager_calls_get_supported_links(mock_map_to_response: mock.Mock):
    aggregator_id = 123

    with mock.patch("envoy.server.crud.link.get_supported_links") as get_supported_links:
        _ = await DeviceCapabilityManager.fetch_device_capability(aggregator_id=aggregator_id)

    get_supported_links.assert_awaited_once_with(DeviceCapabilityResponse, aggregator_id)


@pytest.mark.anyio
async def test_device_capability_manager_calls_map_to_response():
    aggregator_id = 123
    links = mock.Mock()

    with mock.patch("envoy.server.crud.link.get_supported_links", return_value=links), mock.patch(
        "envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response"
    ) as map_to_response:
        _ = await DeviceCapabilityManager.fetch_device_capability(aggregator_id=aggregator_id)

    map_to_response.assert_called_once_with(links)
