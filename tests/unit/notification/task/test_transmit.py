import unittest.mock as mock
from datetime import timedelta
from http import HTTPStatus
from typing import Union
from uuid import uuid4

import pytest
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from httpx import Response

from envoy.notification.exception import NotificationError
from envoy.notification.task.transmit import (
    HEADER_NOTIFICATION_ID,
    HEADER_SUBSCRIPTION_ID,
    attempt_to_retry_delay,
    do_transmit_notification,
    schedule_retry_transmission,
    transmit_notification,
)
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
    notification_id = str(uuid4())
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
    notification_id = str(uuid4())
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


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response_code",
    [
        (HTTPStatus.OK),
        (HTTPStatus.NO_CONTENT),
        (HTTPStatus.ACCEPTED),
        (HTTPStatus.CREATED),
        (HTTPStatus.ALREADY_REPORTED),
    ],
)
@mock.patch("envoy.notification.task.transmit.AsyncClient")
async def test_do_transmit_notification_success(mock_AsyncClient: mock.MagicMock, response_code: HTTPStatus):
    """Tests various common success status codes to see if the logic flows correctly on success"""
    remote_uri = "http://foo.bar/example?a=b"
    content = "MY POST CONTENT"
    subscription_href = "/my/sub/123"
    notification_id = str(uuid4())
    attempt = 4

    mocked_client = MockedAsyncClient(Response(status_code=response_code, content="Mock response content"))
    mock_AsyncClient.return_value = mocked_client

    # should return True on successful transmit
    assert await do_transmit_notification(remote_uri, content, subscription_href, notification_id, attempt)

    # Should have had an outgoing request
    assert len(mocked_client.logged_requests) == 1
    assert mocked_client.call_count_by_method_uri[(HTTPMethod.POST, remote_uri)] == 1
    assert mocked_client.logged_requests[0].uri == remote_uri
    assert mocked_client.logged_requests[0].content == content
    headers = mocked_client.logged_requests[0].headers
    assert headers is not None
    assert headers.get(HEADER_SUBSCRIPTION_ID, None) == subscription_href
    assert headers.get(HEADER_NOTIFICATION_ID, None) == str(notification_id)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response_code",
    [
        (HTTPStatus.BAD_REQUEST),
        (HTTPStatus.UNAUTHORIZED),
        (HTTPStatus.FORBIDDEN),
        (HTTPStatus.NOT_FOUND),
        (HTTPStatus.MOVED_PERMANENTLY),
    ],
)
@mock.patch("envoy.notification.task.transmit.AsyncClient")
async def test_do_transmit_notification_immediately_abort(mock_AsyncClient: mock.MagicMock, response_code: HTTPStatus):
    """Tests various status codes that should abort any attempts to retry (eg - Unauthorised)"""
    remote_uri = "http://foo.bar/example?a=b"
    content = "MY POST CONTENT"
    subscription_href = "/my/sub/123"
    notification_id = str(uuid4())
    attempt = 4

    mocked_client = MockedAsyncClient(Response(status_code=response_code, content="Mock response content"))
    mock_AsyncClient.return_value = mocked_client

    # should return False on an abort
    assert not await do_transmit_notification(remote_uri, content, subscription_href, notification_id, attempt)

    # Should have had an outgoing request
    assert len(mocked_client.logged_requests) == 1
    assert mocked_client.call_count_by_method_uri[(HTTPMethod.POST, remote_uri)] == 1
    assert mocked_client.logged_requests[0].uri == remote_uri
    assert mocked_client.logged_requests[0].content == content
    headers = mocked_client.logged_requests[0].headers
    assert headers is not None
    assert headers.get(HEADER_SUBSCRIPTION_ID, None) == subscription_href
    assert headers.get(HEADER_NOTIFICATION_ID, None) == str(notification_id)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response_code_or_ex",
    [
        (HTTPStatus.INTERNAL_SERVER_ERROR),
        (HTTPStatus.GATEWAY_TIMEOUT),
        (HTTPStatus.SERVICE_UNAVAILABLE),
        (Exception("Mock connection error")),
    ],
)
@mock.patch("envoy.notification.task.transmit.AsyncClient")
async def test_do_transmit_notification_potential_retry(
    mock_AsyncClient: mock.MagicMock, response_code_or_ex: Union[HTTPStatus, Exception]
):
    """Tests various status codes that should raise an error indicating a retry might be in order (eg - HTTP 500)"""
    remote_uri = "http://foo.bar/example?a=b"
    content = "MY POST CONTENT"
    subscription_href = "/my/sub/123"
    notification_id = str(uuid4())
    attempt = 4

    response = (
        response_code_or_ex
        if isinstance(response_code_or_ex, Exception)
        else Response(status_code=response_code_or_ex, content="Mock response content")
    )
    mocked_client = MockedAsyncClient(response)
    mock_AsyncClient.return_value = mocked_client

    # should raise error on retry
    with pytest.raises(NotificationError):
        await do_transmit_notification(remote_uri, content, subscription_href, notification_id, attempt)

    # Should have had an outgoing request
    assert mocked_client.call_count_by_method_uri[(HTTPMethod.POST, remote_uri)] == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response_value",
    [
        (True),
        (False),
    ],
)
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
@mock.patch("envoy.notification.task.transmit.schedule_retry_transmission")
async def test_transmit_notification_no_retry(
    mock_schedule_retry_transmission: mock.MagicMock,
    mock_do_transmit_notification: mock.MagicMock,
    response_value: bool,
):
    """Simple sanity check - do the method correctly offload to do_transmit_notification"""
    remote_uri = "http://example.foo.bar/path?a=b"
    content = "my content to send"
    subscription_href = "/my/href"
    notification_id = str(uuid4())
    attempt = 3
    broker = create_mock_broker()

    mock_do_transmit_notification.return_value = response_value
    await transmit_notification(remote_uri, content, subscription_href, notification_id, attempt, broker)

    mock_do_transmit_notification.assert_called_once_with(
        remote_uri, content, subscription_href, notification_id, attempt
    )
    mock_schedule_retry_transmission.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
@mock.patch("envoy.notification.task.transmit.schedule_retry_transmission")
async def test_transmit_notification_with_retry(
    mock_schedule_retry_transmission: mock.MagicMock, mock_do_transmit_notification: mock.MagicMock
):
    """Simple sanity check - do the method correctly utilise schedule_retry_transmission on Error"""
    remote_uri = "http://example.foo.bar/path?a=b"
    content = "my content to send"
    subscription_href = "/my/href"
    notification_id = str(uuid4())
    attempt = 3
    broker = create_mock_broker()

    mock_do_transmit_notification.side_effect = NotificationError("My mock error")
    await transmit_notification(remote_uri, content, subscription_href, notification_id, attempt, broker)

    mock_do_transmit_notification.assert_called_once_with(
        remote_uri, content, subscription_href, notification_id, attempt
    )
    mock_schedule_retry_transmission.assert_called_once_with(
        broker, remote_uri, content, subscription_href, notification_id, attempt
    )
