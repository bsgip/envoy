import unittest.mock as mock
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Optional, Union
from uuid import uuid4

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from assertical.fixtures.postgres import generate_async_session
from httpx import Response
from sqlalchemy import select

from envoy.notification.exception import NotificationTransmitError
from envoy.notification.task.transmit import (
    HEADER_CONTENT_TYPE,
    HEADER_NOTIFICATION_ID,
    HEADER_SUBSCRIPTION_ID,
    TransmitResult,
    attempt_to_retry_delay,
    create_transmit_notification_log,
    do_transmit_notification,
    safely_log_transmit_result,
    schedule_retry_transmission,
    transmit_notification,
)
from envoy.server.api.response import SEP_XML_MIME
from envoy.server.model.subscription import TransmitNotificationLog
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


@pytest.mark.parametrize(
    "result, expected_ms, expected_code",
    [
        (
            TransmitResult(
                True,
                datetime(2022, 11, 14, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2022, 11, 14, 1, 1, 0, tzinfo=timezone.utc),
                200,
            ),
            60000,
            200,
        ),
        (
            TransmitResult(
                False,
                datetime(2023, 11, 14, 2, 0, 0, tzinfo=timezone.utc),
                datetime(2023, 11, 14, 2, 1, 1, tzinfo=timezone.utc),
                404,
            ),
            61000,
            404,
        ),
        (
            TransmitResult(
                False,
                datetime(2023, 11, 14, 2, 0, 0, tzinfo=timezone.utc),
                datetime(2023, 11, 14, 2, 1, 1, tzinfo=timezone.utc),
                None,
            ),
            61000,
            -1,
        ),
        (
            NotificationTransmitError(
                "foo",
                datetime(2023, 11, 14, 2, 0, 1, tzinfo=timezone.utc),
                datetime(2023, 11, 14, 2, 0, 1, 100000, tzinfo=timezone.utc),
                504,
            ),
            100,
            504,
        ),
        (
            NotificationTransmitError(
                "foo",
                datetime(2023, 11, 14, 2, 0, 1, tzinfo=timezone.utc),
                datetime(2023, 11, 14, 2, 0, 1, 100000, tzinfo=timezone.utc),
                None,
            ),
            100,
            -1,
        ),
    ],
)
def test_create_transmit_notification_log(result, expected_ms: int, expected_code: Optional[int]):
    attempt = 123
    subscription_id = 456
    content = "abc-123 def"
    log = create_transmit_notification_log(result, attempt, subscription_id, content)
    assert isinstance(log, TransmitNotificationLog)
    assert log.transmit_notification_log_id is None, "dont set PK"
    assert log.transmit_duration_ms == expected_ms
    assert log.http_status_code == expected_code
    assert log.attempt == attempt
    assert log.subscription_id_snapshot == subscription_id
    assert log.notification_size_bytes == len(content)


@pytest.mark.anyio
async def test_safely_log_transmit_result(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        await safely_log_transmit_result(
            session,
            NotificationTransmitError(
                "foo",
                datetime(2023, 11, 14, 2, 0, 1, tzinfo=timezone.utc),
                datetime(2023, 11, 14, 2, 0, 1, 100000, tzinfo=timezone.utc),
                None,
            ),
            2,
            99,
            "my content",
        )

    async with generate_async_session(pg_base_config) as session:
        logs = (await session.execute(select(TransmitNotificationLog))).scalars().all()
        assert len(logs) == 1
        assert logs[0].http_status_code == -1
        assert logs[0].subscription_id_snapshot == 99


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
    subscription_id = 2

    mock_attempt_to_retry_delay.return_value = None

    await schedule_retry_transmission(
        mock_broker, remote_uri, content, subscription_href, subscription_id, notification_id, attempt
    )

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
    subscription_id = 2
    delay_seconds = 123

    mock_attempt_to_retry_delay.return_value = timedelta(seconds=delay_seconds)

    await schedule_retry_transmission(
        mock_broker, remote_uri, content, subscription_href, subscription_id, notification_id, attempt
    )

    assert_task_kicked_n_times(mock_transmit_notification, 1)
    assert_task_kicked_with_broker_delay_and_args(
        mock_transmit_notification,
        mock_broker,
        delay_seconds,
        remote_uri=remote_uri,
        content=content,
        subscription_href=subscription_href,
        subscription_id=subscription_id,
        notification_id=notification_id,
        attempt=attempt + 1,
    )

    mock_attempt_to_retry_delay.assert_called_once_with(attempt)


@pytest.mark.anyio
@pytest.mark.parametrize("disable_tls_verify, expected_verify", [(False, True), (True, False)])
@mock.patch("envoy.notification.task.transmit.AsyncClient")
async def test_do_transmit_notification_tls_verify(
    mock_AsyncClient: mock.MagicMock, disable_tls_verify: bool, expected_verify: bool
):
    """Tests that the disable_tls_verify flag is correctly passed through to AsyncClient as verify"""
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content="Mock response content"))
    mock_AsyncClient.return_value = mocked_client

    await do_transmit_notification(
        "http://foo.bar/example",
        "content",
        "/sub/1",
        str(uuid4()),
        0,
        disable_tls_verify=disable_tls_verify,
    )

    mock_AsyncClient.assert_called_once_with(timeout=mock.ANY, verify=expected_verify)


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
    transmit_result = await do_transmit_notification(remote_uri, content, subscription_href, notification_id, attempt)
    assert isinstance(transmit_result, TransmitResult)
    assert transmit_result.success
    assert transmit_result.http_status_code == response_code
    assert_nowish(transmit_result.transmit_start)
    assert_nowish(transmit_result.transmit_end)
    assert transmit_result.transmit_start.tzinfo, "Should be TZ aware"
    assert transmit_result.transmit_end.tzinfo, "Should be TZ aware"
    assert transmit_result.transmit_start <= transmit_result.transmit_end

    # Should have had an outgoing request
    assert len(mocked_client.logged_requests) == 1
    assert mocked_client.call_count_by_method_uri[(HTTPMethod.POST, remote_uri)] == 1
    assert mocked_client.logged_requests[0].uri == remote_uri
    assert mocked_client.logged_requests[0].content == content
    headers = mocked_client.logged_requests[0].headers
    assert headers is not None
    assert headers.get(HEADER_SUBSCRIPTION_ID, None) == subscription_href
    assert headers.get(HEADER_NOTIFICATION_ID, None) == str(notification_id)
    assert headers.get(HEADER_CONTENT_TYPE, None) == SEP_XML_MIME


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
    transmit_result = await do_transmit_notification(remote_uri, content, subscription_href, notification_id, attempt)
    assert not transmit_result.success
    assert transmit_result.http_status_code == response_code
    assert_nowish(transmit_result.transmit_start)
    assert_nowish(transmit_result.transmit_end)
    assert transmit_result.transmit_start.tzinfo, "Should be TZ aware"
    assert transmit_result.transmit_end.tzinfo, "Should be TZ aware"
    assert transmit_result.transmit_start <= transmit_result.transmit_end

    # Should have had an outgoing request
    assert len(mocked_client.logged_requests) == 1
    assert mocked_client.call_count_by_method_uri[(HTTPMethod.POST, remote_uri)] == 1
    assert mocked_client.logged_requests[0].uri == remote_uri
    assert mocked_client.logged_requests[0].content == content
    headers = mocked_client.logged_requests[0].headers
    assert headers is not None
    assert headers.get(HEADER_SUBSCRIPTION_ID, None) == subscription_href
    assert headers.get(HEADER_NOTIFICATION_ID, None) == str(notification_id)
    assert headers.get(HEADER_CONTENT_TYPE, None) == SEP_XML_MIME


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
    with pytest.raises(NotificationTransmitError) as excinfo:
        await do_transmit_notification(remote_uri, content, subscription_href, notification_id, attempt)

    assert_nowish(excinfo.value.transmit_start)
    assert_nowish(excinfo.value.transmit_end)
    assert excinfo.value.transmit_start.tzinfo, "Should be TZ aware"
    assert excinfo.value.transmit_end.tzinfo, "Should be TZ aware"
    assert excinfo.value.transmit_start <= excinfo.value.transmit_end
    if isinstance(response_code_or_ex, HTTPStatus):
        assert excinfo.value.http_status_code == response_code_or_ex
    else:
        assert excinfo.value.http_status_code is None

    # Should have had an outgoing request
    assert mocked_client.call_count_by_method_uri[(HTTPMethod.POST, remote_uri)] == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "transmit_result",
    [
        TransmitResult(
            True,
            datetime(2022, 11, 14, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 11, 14, 1, 1, 0, tzinfo=timezone.utc),
            200,
        ),
        TransmitResult(
            False,
            datetime(2023, 11, 14, 2, 0, 0, tzinfo=timezone.utc),
            datetime(2023, 11, 14, 2, 1, 1, tzinfo=timezone.utc),
            404,
        ),
    ],
)
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
@mock.patch("envoy.notification.task.transmit.schedule_retry_transmission")
@mock.patch("envoy.notification.task.transmit.safely_log_transmit_result")
async def test_transmit_notification_no_retry(
    mock_safely_log_transmit_result: mock.MagicMock,
    mock_schedule_retry_transmission: mock.MagicMock,
    mock_do_transmit_notification: mock.MagicMock,
    transmit_result: TransmitResult,
):
    """Simple sanity check - do the method correctly offload to do_transmit_notification"""
    remote_uri = "http://example.foo.bar/path?a=b"
    content = "my content to send"
    subscription_href = "/my/href"
    notification_id = str(uuid4())
    attempt = 3
    subscription_id = 4
    broker = create_mock_broker()
    session = create_mock_session()

    mock_do_transmit_notification.return_value = transmit_result
    await transmit_notification(
        remote_uri,
        content,
        subscription_href,
        subscription_id,
        notification_id,
        attempt,
        broker,
        session,
        disable_tls_verify=False,
    )

    mock_safely_log_transmit_result.assert_called_once()
    mock_do_transmit_notification.assert_called_once_with(
        remote_uri,
        content,
        subscription_href,
        notification_id,
        attempt,
        disable_tls_verify=False,
    )
    mock_schedule_retry_transmission.assert_not_called()
    assert_mock_session(session)


@pytest.mark.anyio
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
@mock.patch("envoy.notification.task.transmit.schedule_retry_transmission")
@mock.patch("envoy.notification.task.transmit.safely_log_transmit_result")
async def test_transmit_notification_with_retry(
    mock_safely_log_transmit_result: mock.MagicMock,
    mock_schedule_retry_transmission: mock.MagicMock,
    mock_do_transmit_notification: mock.MagicMock,
):
    """Simple sanity check - do the method correctly utilise schedule_retry_transmission on Error"""
    remote_uri = "http://example.foo.bar/path?a=b"
    content = "my content to send"
    subscription_href = "/my/href"
    subscription_id = 4
    notification_id = str(uuid4())
    attempt = 3
    broker = create_mock_broker()
    session = create_mock_session()

    mock_do_transmit_notification.side_effect = NotificationTransmitError(
        "My mock error",
        datetime(2022, 11, 14, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2022, 11, 14, 1, 0, 1, tzinfo=timezone.utc),
        500,
    )
    await transmit_notification(
        remote_uri,
        content,
        subscription_href,
        subscription_id,
        notification_id,
        attempt,
        broker,
        session,
        disable_tls_verify=False,
    )

    mock_safely_log_transmit_result.assert_called_once()
    mock_do_transmit_notification.assert_called_once_with(
        remote_uri,
        content,
        subscription_href,
        notification_id,
        attempt,
        disable_tls_verify=False,
    )
    mock_schedule_retry_transmission.assert_called_once_with(
        broker, remote_uri, content, subscription_href, subscription_id, notification_id, attempt
    )
    assert_mock_session(session)
