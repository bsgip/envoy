import unittest.mock as mock

import pytest
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse

from envoy.server.manager.device_capability import DeviceCapabilityManager
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID
from envoy.server.request_scope import RawRequestClaims


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
async def test_device_capability_manager_calls_get_supported_links(mock_map_to_response: mock.Mock):
    session = mock.Mock()
    scope: RawRequestClaims = generate_class_instance(RawRequestClaims)

    with mock.patch("envoy.server.crud.link.get_supported_links") as get_supported_links:
        _ = await DeviceCapabilityManager.fetch_device_capability(session=session, scope=scope)

    get_supported_links.assert_awaited_once_with(
        session=session,
        scope=scope,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        model=DeviceCapabilityResponse,
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
async def test_device_capability_manager_calls_get_supported_links_agg_end_device(mock_map_to_response: mock.Mock):
    session = mock.Mock()
    scope: RawRequestClaims = generate_class_instance(RawRequestClaims, aggregator_id=None)

    with mock.patch("envoy.server.crud.link.get_supported_links") as get_supported_links:
        _ = await DeviceCapabilityManager.fetch_device_capability(session=session, scope=scope)

    get_supported_links.assert_awaited_once_with(
        session=session,
        scope=scope,
        aggregator_id=NULL_AGGREGATOR_ID,
        site_id=scope.site_id,
        model=DeviceCapabilityResponse,
    )


@pytest.mark.anyio
async def test_device_capability_manager_calls_map_to_response():
    links = mock.Mock()
    scope: RawRequestClaims = generate_class_instance(RawRequestClaims)

    with mock.patch("envoy.server.crud.link.get_supported_links", return_value=links), mock.patch(
        "envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response"
    ) as map_to_response:
        _ = await DeviceCapabilityManager.fetch_device_capability(session=mock.Mock(), scope=scope)

    map_to_response.assert_called_once_with(scope=scope, links=links)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_unregistered_response")
async def test_device_capability_manager_unregistered_scope(mock_map_to_unregistered_response: mock.Mock):
    """Tests that an unregistered scope short-circuits into the unregistered response"""

    scope: RawRequestClaims = generate_class_instance(RawRequestClaims, aggregator_id=None, site_id=None)
    await DeviceCapabilityManager.fetch_device_capability(session=mock.Mock(), scope=scope)
    mock_map_to_unregistered_response.assert_called_once_with(scope)
