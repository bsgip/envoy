import unittest.mock as mock
from datetime import timedelta
from uuid import uuid4

import pytest

from envoy.notification.task.transmit import attempt_to_retry_delay, schedule_retry_transmission
from tests.unit.notification.mocks import (
    assert_task_kicked_n_times,
    assert_task_kicked_with_broker_delay_and_args,
    configure_mock_task,
    create_mock_broker,
)


def test_attempt_to_retry_delay():
    last_delay: timedelta = timedelta(seconds=0)
    for attempt in range(100):
        this_delay = attempt_to_retry_delay(attempt)
        if this_delay is None:
            break

        assert this_delay >= last_delay, "Delays should increase (or at least stay constant)"

    assert attempt > 0, "There should be at least 1 retry"
    assert this_delay is None, "The attempt delays should dry up after a certain number of requests"


@pytest.mark.anyio
@mock.patch("envoy.notification.task.transmit.transmit_notification")
@mock.patch("envoy.notification.task.transmit.attempt_to_retry_delay")
async def test_schedule_retry_transmission_too_many_attempts(
    mock_attempt_to_retry_delay: mock.MagicMock, mock_transmit_notification: mock.MagicMock
):
    """Tests that if attempt_to_retry_delay returns None - this does nothing (i.e. aborts the retry)"""
    configure_mock_task(mock_transmit_notification)
    mock_broker = create_mock_broker()
    remote_uri = "http://foo.bar/example?a=b"
    content = "MY POST CONTENT"
    subscription_href = "/my/sub/123"
    notification_id = uuid4()
    attempt = 1

    mock_attempt_to_retry_delay.return_value = None

    await schedule_retry_transmission(mock_broker, remote_uri, content, subscription_href, notification_id, attempt)

    assert_task_kicked_n_times(mock_transmit_notification, 0)
    mock_attempt_to_retry_delay.assert_called_once_with(attempt)


@pytest.mark.anyio
@mock.patch("envoy.notification.task.transmit.transmit_notification")
@mock.patch("envoy.notification.task.transmit.attempt_to_retry_delay")
async def test_schedule_retry_transmission(
    mock_attempt_to_retry_delay: mock.MagicMock, mock_transmit_notification: mock.MagicMock
):
    """Tests that rescheduling enqueues another transmission"""
    configure_mock_task(mock_transmit_notification)
    mock_broker = create_mock_broker()
    remote_uri = "http://foo.bar/example?a=b"
    content = "MY POST CONTENT"
    subscription_href = "/my/sub/123"
    notification_id = uuid4()
    attempt = 1
    delay_seconds = 123

    mock_attempt_to_retry_delay.return_value = timedelta(seconds=delay_seconds)

    await schedule_retry_transmission(mock_broker, remote_uri, content, subscription_href, notification_id, attempt)

    assert_task_kicked_n_times(mock_transmit_notification, 1)
    assert_task_kicked_with_broker_delay_and_args(
        mock_transmit_notification,
        mock_broker,
        delay_seconds,
        remote_uri=remote_uri,
        content=content,
        subscription_href=subscription_href,
        notification_id=notification_id,
        attempt=attempt + 1,
    )

    mock_attempt_to_retry_delay.assert_called_once_with(attempt)
