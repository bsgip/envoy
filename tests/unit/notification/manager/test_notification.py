import unittest.mock as mock
from datetime import datetime

import pytest

from envoy.notification.manager.notification import NotificationManager
from envoy.server.model.subscription import SubscriptionResource
from tests.unit.notification.mocks import (
    assert_task_kicked_n_times,
    assert_task_kicked_with_broker_and_args,
    configure_mock_task,
    create_mock_broker,
)


@pytest.mark.asyncio
@mock.patch("envoy.notification.manager.notification.check_db_change_or_delete")
@mock.patch("envoy.notification.manager.notification.get_enabled_broker")
async def test_notify_changed_deleted_entities_no_config(
    mock_get_enabled_broker: mock.MagicMock, mock_check_db_change_or_delete: mock.MagicMock
):
    resource = SubscriptionResource
    timestamp = datetime(2024, 3, 4, 5, 6)

    configure_mock_task(mock_check_db_change_or_delete)
    mock_get_enabled_broker.return_value = None

    # Returns false
    assert not await NotificationManager.notify_changed_deleted_entities(resource, timestamp)

    assert_task_kicked_n_times(mock_check_db_change_or_delete, 0)
    mock_get_enabled_broker.assert_called_once()


@pytest.mark.asyncio
@mock.patch("envoy.notification.manager.notification.check_db_change_or_delete")
@mock.patch("envoy.notification.manager.notification.get_enabled_broker")
async def test_notify_changed_deleted_entities_with_config(
    mock_get_enabled_broker: mock.MagicMock, mock_check_db_change_or_delete: mock.MagicMock
):
    resource = SubscriptionResource
    timestamp = datetime(2024, 3, 4, 5, 6)

    mock_broker = create_mock_broker()
    configure_mock_task(mock_check_db_change_or_delete)
    mock_get_enabled_broker.return_value = mock_broker

    # Returns true
    assert await NotificationManager.notify_changed_deleted_entities(resource, timestamp)

    assert_task_kicked_n_times(mock_check_db_change_or_delete, 1)
    assert_task_kicked_with_broker_and_args(
        mock_check_db_change_or_delete, mock_broker, resource=resource, timestamp_epoch=timestamp.timestamp()
    )
    mock_get_enabled_broker.assert_called_once()


@pytest.mark.asyncio
@mock.patch("envoy.notification.manager.notification.check_db_change_or_delete")
@mock.patch("envoy.notification.manager.notification.get_enabled_broker")
async def test_notify_changed_deleted_entities_with_config_on_error(
    mock_get_enabled_broker: mock.MagicMock, mock_check_db_change_or_delete: mock.MagicMock
):
    resource = SubscriptionResource
    timestamp = datetime(2024, 3, 4, 5, 6)

    mock_broker = create_mock_broker()
    configure_mock_task(mock_check_db_change_or_delete, raise_on_kiq=Exception("mock error"))
    mock_get_enabled_broker.return_value = mock_broker

    # Returns false
    assert not await NotificationManager.notify_changed_deleted_entities(resource, timestamp)

    assert_task_kicked_n_times(mock_check_db_change_or_delete, 1)
    mock_get_enabled_broker.assert_called_once()
