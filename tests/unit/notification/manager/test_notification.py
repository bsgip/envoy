import unittest.mock as mock
from datetime import datetime

import pytest
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session

from envoy.notification.manager.notification import NotificationManager
from envoy.server.model.subscription import NotificationCheck, SubscriptionResource


@pytest.mark.asyncio
@mock.patch("envoy.notification.manager.notification.notifications_enabled")
async def test_notify_changed_deleted_entities_notifications_disabled(mock_notifications_enabled: mock.MagicMock):
    """When notifications are disabled - it's a no-op returning False and nothing is added to the session"""
    resource = SubscriptionResource.SITE
    timestamp = datetime(2024, 3, 4, 5, 6)

    mock_notifications_enabled.return_value = False
    mock_session = create_mock_session()

    assert not await NotificationManager.notify_changed_deleted_entities(mock_session, resource, timestamp)

    mock_session.add.assert_not_called()
    assert_mock_session(mock_session, committed=False)


@pytest.mark.asyncio
@mock.patch("envoy.notification.manager.notification.notifications_enabled")
async def test_notify_changed_deleted_entities_enqueues_check(mock_notifications_enabled: mock.MagicMock):
    """When notifications are enabled - a NotificationCheck is added to the supplied session (but NOT committed - the
    caller commits it atomically with the data change) and it returns True"""
    resource = SubscriptionResource.SITE
    timestamp = datetime(2024, 3, 4, 5, 6)

    mock_notifications_enabled.return_value = True
    mock_session = create_mock_session()

    assert await NotificationManager.notify_changed_deleted_entities(mock_session, resource, timestamp)

    mock_session.add.assert_called_once()
    enqueued = mock_session.add.call_args.args[0]
    assert isinstance(enqueued, NotificationCheck)
    assert enqueued.resource_type == resource
    assert enqueued.changed_time == timestamp

    # The writer must NOT commit - the originating request commits the check row alongside its data (outbox)
    assert_mock_session(mock_session, committed=False)
