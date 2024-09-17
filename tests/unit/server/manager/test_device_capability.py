import unittest.mock as mock

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse

from envoy.server.manager.device_capability import DeviceCapabilityManager
from envoy.server.model.site import Site
from envoy.server.request_scope import CertificateType, UnregisteredRequestScope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_unregistered_response")
@mock.patch("envoy.server.manager.device_capability.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.device_capability.link.get_supported_links")
async def test_device_capability_manager_aggregator_scope(
    mock_get_supported_links: mock.Mock,
    mock_select_single_site_with_lfdi: mock.Mock,
    mock_map_to_unregistered_response: mock.Mock,
    mock_map_to_response: mock.Mock,
):
    """Tests that device cert that is registered returns properly offloads to the full response"""

    # Arrange
    mock_session = create_mock_session()
    mock_get_supported_links.return_value = mock.Mock()
    mock_map_to_response.return_value = mock.Mock()
    scope: UnregisteredRequestScope = generate_class_instance(
        UnregisteredRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE
    )

    # Act
    assert (
        await DeviceCapabilityManager.fetch_device_capability(session=mock_session, scope=scope)
    ) is mock_map_to_response.return_value

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_map_to_unregistered_response.assert_not_called()
    mock_select_single_site_with_lfdi.assert_not_called()
    mock_get_supported_links.assert_called_once_with(
        session=mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=None,
        scope=scope,
        model=DeviceCapabilityResponse,
    )
    mock_map_to_response.assert_called_once_with(scope=scope, links=mock_get_supported_links.return_value)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_unregistered_response")
@mock.patch("envoy.server.manager.device_capability.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.device_capability.link.get_supported_links")
async def test_device_capability_manager_unregistered_device_scope(
    mock_get_supported_links: mock.Mock,
    mock_select_single_site_with_lfdi: mock.Mock,
    mock_map_to_unregistered_response: mock.Mock,
    mock_map_to_response: mock.Mock,
):
    """Tests that device cert that isn't yet registered returns the unregistered device cap response"""

    # Arrange
    mock_session = create_mock_session()
    mock_select_single_site_with_lfdi.return_value = None
    mock_map_to_unregistered_response.return_value = mock.Mock()
    scope: UnregisteredRequestScope = generate_class_instance(
        UnregisteredRequestScope, source=CertificateType.DEVICE_CERTIFICATE
    )

    # Act
    assert (
        await DeviceCapabilityManager.fetch_device_capability(session=mock_session, scope=scope)
    ) is mock_map_to_unregistered_response.return_value

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_map_to_unregistered_response.assert_called_once_with(scope)
    mock_select_single_site_with_lfdi.assert_called_once_with(mock_session, scope.lfdi, scope.aggregator_id)
    mock_get_supported_links.assert_not_called()
    mock_map_to_response.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_unregistered_response")
@mock.patch("envoy.server.manager.device_capability.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.device_capability.link.get_supported_links")
async def test_device_capability_manager_registered_device_scope(
    mock_get_supported_links: mock.Mock,
    mock_select_single_site_with_lfdi: mock.Mock,
    mock_map_to_unregistered_response: mock.Mock,
    mock_map_to_response: mock.Mock,
):
    """Tests that device cert that is registered returns properly offloads to the full response"""

    # Arrange
    mock_session = create_mock_session()
    existing_site: Site = generate_class_instance(Site, seed=1001)
    mock_select_single_site_with_lfdi.return_value = existing_site
    mock_get_supported_links.return_value = mock.Mock()
    mock_map_to_response.return_value = mock.Mock()
    scope: UnregisteredRequestScope = generate_class_instance(
        UnregisteredRequestScope, source=CertificateType.DEVICE_CERTIFICATE
    )

    # Act
    assert (
        await DeviceCapabilityManager.fetch_device_capability(session=mock_session, scope=scope)
    ) is mock_map_to_response.return_value

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_map_to_unregistered_response.assert_not_called()
    mock_select_single_site_with_lfdi.assert_called_once_with(mock_session, scope.lfdi, scope.aggregator_id)
    mock_get_supported_links.assert_called_once_with(
        session=mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=existing_site.site_id,
        scope=scope,
        model=DeviceCapabilityResponse,
    )
    mock_map_to_response.assert_called_once_with(scope=scope, links=mock_get_supported_links.return_value)
