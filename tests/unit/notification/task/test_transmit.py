import ssl
import unittest.mock as mock
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import uuid4

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from assertical.fixtures.postgres import SingleAsyncEngineState, generate_async_session
from httpx import Response
from sqlalchemy import func, select

from envoy.notification.exception import NotificationTransmitError
from envoy.notification.task.transmit import (
    HEADER_CONTENT_TYPE,
    HEADER_NOTIFICATION_ID,
    HEADER_SUBSCRIPTION_ID,
    RETRY_DELAYS,
    TransmitResult,
    attempt_to_retry_delay,
    create_transmit_notification_log,
    do_transmit_notification,
    process_transmit_batch,
)
from envoy.server.api.response import SEP_XML_MIME
from envoy.server.manager.time import utc_now
from envoy.server.model.subscription import NotificationDeadLetter, NotificationTransmit, TransmitNotificationLog


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
                datetime(2022, 11, 14, 1, 0, 0, tzinfo=UTC),
                datetime(2022, 11, 14, 1, 1, 0, tzinfo=UTC),
                200,
            ),
            60000,
            200,
        ),
        (
            TransmitResult(
                False,
                datetime(2023, 11, 14, 2, 0, 0, tzinfo=UTC),
                datetime(2023, 11, 14, 2, 1, 1, tzinfo=UTC),
                404,
            ),
            61000,
            404,
        ),
        (
            TransmitResult(
                False,
                datetime(2023, 11, 14, 2, 0, 0, tzinfo=UTC),
                datetime(2023, 11, 14, 2, 1, 1, tzinfo=UTC),
                None,
            ),
            61000,
            -1,
        ),
        (
            NotificationTransmitError(
                "foo",
                datetime(2023, 11, 14, 2, 0, 1, tzinfo=UTC),
                datetime(2023, 11, 14, 2, 0, 1, 100000, tzinfo=UTC),
                504,
            ),
            100,
            504,
        ),
        (
            NotificationTransmitError(
                "foo",
                datetime(2023, 11, 14, 2, 0, 1, tzinfo=UTC),
                datetime(2023, 11, 14, 2, 0, 1, 100000, tzinfo=UTC),
                None,
            ),
            100,
            -1,
        ),
    ],
)
def test_create_transmit_notification_log(result, expected_ms: int, expected_code: int | None):
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
@pytest.mark.parametrize("verify", [True, False, mock.MagicMock(spec=ssl.SSLContext)])
@mock.patch("envoy.notification.task.transmit.AsyncClient")
async def test_do_transmit_notification_passes_verify(mock_AsyncClient: mock.MagicMock, verify: ssl.SSLContext | bool):
    """The prebuilt verify argument is passed straight through to AsyncClient"""
    mocked_client = MockedAsyncClient(Response(status_code=HTTPStatus.OK, content="Mock response content"))
    mock_AsyncClient.return_value = mocked_client

    await do_transmit_notification("http://foo.bar/example", "content", "/sub/1", str(uuid4()), 0, verify=verify)

    mock_AsyncClient.assert_called_once_with(timeout=mock.ANY, verify=verify)


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
    headers = mocked_client.logged_requests[0].headers_dict
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
    headers = mocked_client.logged_requests[0].headers_dict
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
    mock_AsyncClient: mock.MagicMock, response_code_or_ex: HTTPStatus | Exception
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
            datetime(2022, 11, 14, 1, 0, 0, tzinfo=UTC),
            datetime(2022, 11, 14, 1, 1, 0, tzinfo=UTC),
            200,
        ),
        TransmitResult(
            False,
            datetime(2023, 11, 14, 2, 0, 0, tzinfo=UTC),
            datetime(2023, 11, 14, 2, 1, 1, tzinfo=UTC),
            404,
        ),
    ],
)
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
async def test_process_transmit_batch_no_retry(
    mock_do_transmit_notification: mock.MagicMock,
    transmit_result: TransmitResult,
    pg_empty_config,
):
    """A success deletes the transmit row; a terminal 3xx/4xx dead-letters it. Both log the attempt"""
    engine_state = SingleAsyncEngineState(pg_empty_config)
    try:
        async with generate_async_session(pg_empty_config) as session:
            session.add(
                generate_class_instance(
                    NotificationTransmit, notification_transmit_id=None, attempt=3, execute_after=utc_now()
                )
            )
            await session.commit()

        mock_do_transmit_notification.return_value = transmit_result
        processed = await process_transmit_batch(engine_state.session_maker, True, batch_size=10)  # ty:ignore[invalid-argument-type]  # noqa: E501
        assert processed == 1

        async with generate_async_session(pg_empty_config) as session:
            # The row leaves the active queue and the attempt was logged
            assert (await session.execute(select(func.count()).select_from(NotificationTransmit))).scalar() == 0
            logs = (await session.execute(select(TransmitNotificationLog))).scalars().all()
            assert len(logs) == 1
            assert logs[0].attempt == 3

            # A success is delivered (no dead-letter); a terminal failure is dead-lettered (content preserved)
            dead = (await session.execute(select(NotificationDeadLetter))).scalars().all()
            if transmit_result.success:
                assert len(dead) == 0
            else:
                assert len(dead) == 1
                assert dead[0].attempt == 3
                assert dead[0].http_status_code == transmit_result.http_status_code

        mock_do_transmit_notification.assert_called_once()
    finally:
        await engine_state.dispose()


@pytest.mark.anyio
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
async def test_process_transmit_batch_with_retry(
    mock_do_transmit_notification: mock.MagicMock,
    pg_empty_config,
):
    """A retryable error reschedules the transmit row (attempt+1, execute_after in the future) and logs the attempt"""
    engine_state = SingleAsyncEngineState(pg_empty_config)
    try:
        async with generate_async_session(pg_empty_config) as session:
            session.add(
                generate_class_instance(
                    NotificationTransmit, notification_transmit_id=None, attempt=1, execute_after=utc_now()
                )
            )
            await session.commit()

        mock_do_transmit_notification.side_effect = NotificationTransmitError(
            "My mock error",
            datetime(2022, 11, 14, 1, 0, 0, tzinfo=UTC),
            datetime(2022, 11, 14, 1, 0, 1, tzinfo=UTC),
            500,
        )
        processed = await process_transmit_batch(engine_state.session_maker, True, batch_size=10)  # ty:ignore[invalid-argument-type]  # noqa: E501
        assert processed == 1

        async with generate_async_session(pg_empty_config) as session:
            rows = (await session.execute(select(NotificationTransmit))).scalars().all()
            assert len(rows) == 1, "Row should be rescheduled (not deleted)"
            assert rows[0].attempt == 2
            assert rows[0].execute_after > utc_now(), "Should be rescheduled into the future"

            logs = (await session.execute(select(TransmitNotificationLog))).scalars().all()
            assert len(logs) == 1
            assert logs[0].attempt == 1

            # Rescheduled, not given up on - nothing dead-lettered
            assert (await session.execute(select(func.count()).select_from(NotificationDeadLetter))).scalar() == 0
    finally:
        await engine_state.dispose()


@pytest.mark.anyio
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
async def test_process_transmit_batch_retries_exhausted(
    mock_do_transmit_notification: mock.MagicMock,
    pg_empty_config,
):
    """A retryable error on the final attempt dead-letters the transmit row (no more retries) but still logs it"""
    engine_state = SingleAsyncEngineState(pg_empty_config)
    try:
        async with generate_async_session(pg_empty_config) as session:
            session.add(
                generate_class_instance(
                    NotificationTransmit,
                    notification_transmit_id=None,
                    attempt=len(RETRY_DELAYS),  # attempt_to_retry_delay returns None here -> dead-letter
                    execute_after=utc_now(),
                    content="dead letter content",
                )
            )
            await session.commit()

        mock_do_transmit_notification.side_effect = NotificationTransmitError(
            "My mock error",
            datetime(2022, 11, 14, 1, 0, 0, tzinfo=UTC),
            datetime(2022, 11, 14, 1, 0, 1, tzinfo=UTC),
            500,
        )
        processed = await process_transmit_batch(engine_state.session_maker, True, batch_size=10)  # ty:ignore[invalid-argument-type]  # noqa: E501
        assert processed == 1

        async with generate_async_session(pg_empty_config) as session:
            # Removed from the active queue, the attempt logged, and the notification preserved in the dead-letter table
            assert (await session.execute(select(func.count()).select_from(NotificationTransmit))).scalar() == 0
            assert (await session.execute(select(func.count()).select_from(TransmitNotificationLog))).scalar() == 1

            dead = (await session.execute(select(NotificationDeadLetter))).scalars().all()
            assert len(dead) == 1
            assert dead[0].attempt == len(RETRY_DELAYS)
            assert dead[0].http_status_code == 500
            assert dead[0].content == "dead letter content"
    finally:
        await engine_state.dispose()


@pytest.mark.anyio
@mock.patch("envoy.notification.task.transmit.do_transmit_notification")
async def test_process_transmit_batch_skips_future(
    mock_do_transmit_notification: mock.MagicMock,
    pg_empty_config,
):
    """A row whose execute_after is in the future is not yet due and must not be claimed/sent"""
    engine_state = SingleAsyncEngineState(pg_empty_config)
    try:
        async with generate_async_session(pg_empty_config) as session:
            session.add(
                generate_class_instance(
                    NotificationTransmit,
                    notification_transmit_id=None,
                    attempt=0,
                    execute_after=utc_now() + timedelta(hours=1),
                )
            )
            await session.commit()

        processed = await process_transmit_batch(engine_state.session_maker, True, batch_size=10)  # ty:ignore[invalid-argument-type]  # noqa: E501
        assert processed == 0
        mock_do_transmit_notification.assert_not_called()

        async with generate_async_session(pg_empty_config) as session:
            assert (await session.execute(select(func.count()).select_from(NotificationTransmit))).scalar() == 1
    finally:
        await engine_state.dispose()
