from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock

import pytest
from envoy_schema.server.schema.sep2.error import ErrorResponse
from envoy_schema.server.schema.sep2.types import ReasonCodeType
from sqlalchemy.exc import DBAPIError, IntegrityError

from envoy.server.api.error_handler import (
    dbapi_exception_handler,
    generate_error_response,
    get_dbapi_error_sqlstate,
    http_status_code_to_reason_code,
)
from envoy.server.api.response import SEP_XML_MIME


def test_http_status_code_to_reason_code_nocrash():
    """Just a quick scan of values to make sure the utility functions work with a variety of inputs"""

    # test ints
    for i in range(-600, 600):
        reason_code = http_status_code_to_reason_code(i)
        assert reason_code is not None and isinstance(reason_code, ReasonCodeType), f"Failure at {i}"

    # test enums
    for e in HTTPStatus:
        reason_code = http_status_code_to_reason_code(e)
        assert reason_code is not None and isinstance(reason_code, ReasonCodeType), f"Failure at {e}"

        # test that enum values are equivalent to the enums directly (eg 500 == INTERNAL_SERVER_ERROR)
        assert http_status_code_to_reason_code(e.value) == http_status_code_to_reason_code(e)

    reason_code = http_status_code_to_reason_code(None)  # ty:ignore[invalid-argument-type]
    assert reason_code is not None and isinstance(reason_code, ReasonCodeType)

    reason_code = http_status_code_to_reason_code("401")  # ty:ignore[invalid-argument-type]
    assert reason_code is not None and isinstance(reason_code, ReasonCodeType)


def test_generate_error_response_optional_message_encoding():
    """Test that special chars decode fine (this isn't exhaustive)"""
    message = "My custom message <>&amp;\n\t123#--"
    response = generate_error_response(HTTPStatus.BAD_GATEWAY, message)
    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert response.media_type == SEP_XML_MIME

    # test the message encodes/decodes OK
    error_response: ErrorResponse = ErrorResponse.from_xml(cast(str, response.body))
    assert error_response.message == message
    assert error_response.maxRetryDuration is None


def test_generate_error_response_optional_message_missing():
    """Tests that a none message isn't going to crash anything"""
    response = generate_error_response(HTTPStatus.IM_A_TEAPOT, None)
    assert response.status_code == HTTPStatus.IM_A_TEAPOT
    assert response.media_type == SEP_XML_MIME

    # test the message encodes/decodes OK
    error_response: ErrorResponse = ErrorResponse.from_xml(cast(str, response.body))
    assert error_response.message is None
    assert error_response.maxRetryDuration is None


def test_generate_error_response_optional_retry_duration():
    """Tests that max_retry_duration is encoded"""
    response = generate_error_response(HTTPStatus.OK, max_retry_duration=54321)
    assert response.status_code == HTTPStatus.OK
    assert response.media_type == SEP_XML_MIME

    # test the message encodes/decodes OK
    error_response: ErrorResponse = ErrorResponse.from_xml(cast(str, response.body))
    assert error_response.message is None
    assert error_response.maxRetryDuration == 54321


class _OrigWithSqlState(Exception):
    def __init__(self, sqlstate: str | None):
        super().__init__("orig error")
        self.sqlstate = sqlstate


class _OrigWithPgCode(Exception):
    def __init__(self, pgcode: str | None):
        super().__init__("orig error")
        self.pgcode = pgcode


class _DriverError(Exception):
    def __init__(self, sqlstate: str):
        super().__init__("driver error")
        self.sqlstate = sqlstate


def _chained_orig(sqlstate: str) -> Exception:
    """An orig exception without its own sqlstate whose __cause__ (the raw driver error) has one"""
    orig = Exception("orig error")
    orig.__cause__ = _DriverError(sqlstate)
    return orig


@pytest.mark.parametrize(
    "orig, expected",
    [
        (_OrigWithSqlState("22001"), "22001"),
        (_OrigWithPgCode("22001"), "22001"),
        (_OrigWithSqlState("23505"), "23505"),
        (_OrigWithSqlState(None), None),
        (_OrigWithSqlState(""), None),
        (_chained_orig("22001"), "22001"),
        (Exception("no code"), None),
    ],
)
def test_get_dbapi_error_sqlstate(orig: Exception, expected: str | None):
    assert get_dbapi_error_sqlstate(DBAPIError("SELECT 1", None, orig)) == expected


@pytest.mark.parametrize(
    "exc, expected_status",
    [
        (DBAPIError("UPDATE x", None, _OrigWithSqlState("22001")), HTTPStatus.BAD_REQUEST),
        (DBAPIError("UPDATE x", None, _OrigWithPgCode("22001")), HTTPStatus.BAD_REQUEST),
        (DBAPIError("UPDATE x", None, _chained_orig("22001")), HTTPStatus.BAD_REQUEST),
        (DBAPIError("UPDATE x", None, _OrigWithSqlState("08006")), HTTPStatus.INTERNAL_SERVER_ERROR),  # conn failure
        (IntegrityError("UPDATE x", None, _OrigWithSqlState("23505")), HTTPStatus.INTERNAL_SERVER_ERROR),
        (DBAPIError("UPDATE x", None, Exception("no code")), HTTPStatus.INTERNAL_SERVER_ERROR),
        (Exception("Not a DBAPIError"), HTTPStatus.INTERNAL_SERVER_ERROR),
    ],
)
def test_dbapi_exception_handler(exc: Exception, expected_status: HTTPStatus):
    request = MagicMock()
    response = dbapi_exception_handler(request, exc)
    assert response.status_code == expected_status
    assert response.media_type == SEP_XML_MIME

    error_response: ErrorResponse = ErrorResponse.from_xml(cast(str, response.body))
    if expected_status == HTTPStatus.BAD_REQUEST:
        assert error_response.reasonCode == ReasonCodeType.invalid_request_format
        assert error_response.message
        assert "UPDATE" not in error_response.message, "Internal SQL shouldn't leak"
    else:
        assert error_response.reasonCode == ReasonCodeType.internal_error
        assert error_response.message is None
