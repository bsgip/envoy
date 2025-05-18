import unittest.mock as mock
from datetime import datetime

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session

from envoy.server.manager.device_capability import DeviceCapabilityManager
from envoy.server.model.config.server import RuntimeServerConfig
from envoy.server.model.site import Site
from envoy.server.request_scope import CertificateType, UnregisteredRequestScope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_unregistered_response")
@mock.patch("envoy.server.manager.device_capability.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.device_capability.select_aggregator_site_count")
@mock.patch("envoy.server.manager.device_capability.count_site_reading_types_for_aggregator")
@mock.patch("envoy.server.manager.device_capability.RuntimeServerConfigManager.fetch_current_config")
async def test_device_capability_manager_aggregator_scope(
    mock_fetch_current_config: mock.Mock,
    mock_count_site_reading_types_for_aggregator: mock.Mock,
    mock_select_aggregator_site_count: mock.Mock,
    mock_select_single_site_with_lfdi: mock.Mock,
    mock_map_to_unregistered_response: mock.Mock,
    mock_map_to_response: mock.Mock,
):
    """Tests that device cert that is registered as an aggregator properly offloads to the full response"""

    # Arrange
    mock_session = create_mock_session()
    mock_map_to_response.return_value = mock.Mock()
    scope: UnregisteredRequestScope = generate_class_instance(
        UnregisteredRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE
    )
    mock_select_aggregator_site_count.return_value = 11
    mock_count_site_reading_types_for_aggregator.return_value = 22

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    assert (
        await DeviceCapabilityManager.fetch_device_capability(session=mock_session, scope=scope)
    ) is mock_map_to_response.return_value

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_map_to_unregistered_response.assert_not_called()
    mock_select_single_site_with_lfdi.assert_not_called()

    mock_select_aggregator_site_count.assert_called_once_with(mock_session, scope.aggregator_id, datetime.min)
    mock_count_site_reading_types_for_aggregator.assert_called_once_with(
        mock_session, scope.aggregator_id, None, datetime.min
    )
    mock_map_to_response.assert_called_once_with(
        scope=scope, edev_cnt=12, mup_cnt=22, pollrate_seconds=config.dcap_pollrate_seconds
    )  # The edev count must also include aggregator end device


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_unregistered_response")
@mock.patch("envoy.server.manager.device_capability.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.device_capability.select_aggregator_site_count")
@mock.patch("envoy.server.manager.device_capability.count_site_reading_types_for_aggregator")
async def test_device_capability_manager_unregistered_device_scope(
    mock_count_site_reading_types_for_aggregator: mock.Mock,
    mock_select_aggregator_site_count: mock.Mock,
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
    mock_map_to_unregistered_response.assert_called_once_with(scope=scope)
    mock_select_single_site_with_lfdi.assert_called_once_with(mock_session, scope.lfdi, scope.aggregator_id)
    mock_map_to_response.assert_not_called()
    mock_select_aggregator_site_count.assert_not_called()
    mock_count_site_reading_types_for_aggregator.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_response")
@mock.patch("envoy.server.manager.device_capability.DeviceCapabilityMapper.map_to_unregistered_response")
@mock.patch("envoy.server.manager.device_capability.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.device_capability.select_aggregator_site_count")
@mock.patch("envoy.server.manager.device_capability.count_site_reading_types_for_aggregator")
@mock.patch("envoy.server.manager.device_capability.RuntimeServerConfigManager.fetch_current_config")
async def test_device_capability_manager_registered_device_scope(
    mock_fetch_current_config: mock.Mock,
    mock_count_site_reading_types_for_aggregator: mock.Mock,
    mock_select_aggregator_site_count: mock.Mock,
    mock_select_single_site_with_lfdi: mock.Mock,
    mock_map_to_unregistered_response: mock.Mock,
    mock_map_to_response: mock.Mock,
):
    """Tests that device cert that is registered returns properly offloads to the full response"""

    # Arrange
    mock_session = create_mock_session()
    existing_site: Site = generate_class_instance(Site, seed=1001)
    mock_select_single_site_with_lfdi.return_value = existing_site
    mock_count_site_reading_types_for_aggregator.return_value = 99
    mock_map_to_response.return_value = mock.Mock()
    scope: UnregisteredRequestScope = generate_class_instance(
        UnregisteredRequestScope, source=CertificateType.DEVICE_CERTIFICATE
    )

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    assert (
        await DeviceCapabilityManager.fetch_device_capability(session=mock_session, scope=scope)
    ) is mock_map_to_response.return_value

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_map_to_unregistered_response.assert_not_called()
    mock_select_single_site_with_lfdi.assert_called_once_with(mock_session, scope.lfdi, scope.aggregator_id)
    mock_select_aggregator_site_count.assert_not_called()  # We don't count - just having the edev means we have 1 site
    mock_count_site_reading_types_for_aggregator.assert_called_once_with(
        mock_session, scope.aggregator_id, existing_site.site_id, datetime.min
    )
    mock_map_to_response.assert_called_once_with(
        scope=scope, edev_cnt=1, mup_cnt=99, pollrate_seconds=config.dcap_pollrate_seconds
    )  # 2 edevs, one for the returned edev and one for the virtual aggregator edev
