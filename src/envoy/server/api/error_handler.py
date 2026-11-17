import logging
from http import HTTPStatus

from envoy_schema.server.schema.sep2.error import ErrorResponse
from envoy_schema.server.schema.sep2.types import ReasonCodeType
from fastapi import HTTPException, Request, Response
from lxml.etree import XMLSyntaxError
from pydantic_core import ValidationError
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from envoy.server.api.response import XmlResponse

logger = logging.getLogger(__name__)

# SQLSTATE codes (https://www.postgresql.org/docs/current/errcodes-appendix.html) that indicate the client sent data
# that violates a DB constraint (rather than a server fault) and should be reported as a HTTP BadRequest
SQLSTATE_STRING_DATA_RIGHT_TRUNCATION = "22001"  # eg: "value too long for type character varying(11)"
BAD_REQUEST_SQLSTATES: dict[str, str] = {
    SQLSTATE_STRING_DATA_RIGHT_TRUNCATION: "One or more string values exceed the maximum supported length.",
}


def http_status_code_to_reason_code(status_code: HTTPStatus | int) -> ReasonCodeType:
    if status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return ReasonCodeType.resource_limit_reached
    elif status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
        return ReasonCodeType.internal_error
    else:
        return ReasonCodeType.invalid_request_format


def generate_error_response(
    status_code: HTTPStatus | int, message: str | None = None, max_retry_duration: int | None = None
) -> Response:
    """Generates an XML response loaded with a sep2 Error object"""
    reason_code = http_status_code_to_reason_code(status_code)

    return XmlResponse(
        status_code=status_code,
        content=ErrorResponse(reasonCode=reason_code, message=message, maxRetryDuration=max_retry_duration),
    )


def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException | Exception) -> Response:
    """Handles specific HTTP exceptions"""
    if isinstance(exc, HTTPException) or isinstance(exc, StarletteHTTPException):
        status_code = exc.status_code
        detail = exc.detail
    else:
        status_code = 0
        detail = "Unknown"

    logger.exception(f"{request.path_params} generated status code {status_code} and exception {exc}")

    return generate_error_response(status_code, message=detail)


def validation_exception_handler(request: Request, exc: ValidationError | Exception) -> Response:
    """Handles fastapi validation exceptions that haven't been handled. These usually occur during
    parsing of an incoming model to a Pydantic model and almost always indicate a bad request by the user.

    It can technically arise if we stuff up the creation of a response model but test coverage should be catching
    those cases so I think it's an acceptable 'risk' to just return the validation errors."""

    if not hasattr(exc, "json"):
        return general_exception_handler(request, exc)

    logger.exception(f"{request.path_params} generated validation exception {exc}")
    return generate_error_response(HTTPStatus.BAD_REQUEST, message=exc.json())  # ty:ignore[call-non-callable] # We check for this above


def xml_exception_handler(request: Request, exc: XMLSyntaxError | Exception) -> Response:
    """Handles fastapi XML validation exceptions that haven't been handled. These usually occur during
    parsing of an incoming model to a Pydantic XML model and almost always indicate a bad request by the user.

    It can technically arise if we stuff up the creation of a response model but test coverage should be catching
    those cases so I think it's an acceptable 'risk' to just return the validation errors."""

    if not hasattr(exc, "msg"):
        return general_exception_handler(request, exc)

    logger.exception(f"{request.path_params} generated validation exception {exc}")
    return generate_error_response(HTTPStatus.BAD_REQUEST, message=exc.msg)  # ty:ignore[invalid-argument-type] # This is checked above


def get_dbapi_error_sqlstate(exc: DBAPIError) -> str | None:
    """Extracts the (postgres) SQLSTATE code from the underlying DBAPI error (if available). Different drivers expose
    this differently - asyncpg (via SQLAlchemy's adapter) exposes sqlstate, psycopg exposes pgcode/sqlstate"""
    orig = exc.orig
    for attr in ("sqlstate", "pgcode"):
        code = getattr(orig, attr, None)
        if isinstance(code, str) and code:
            return code

    # Fallback to the original driver exception (if it was chained)
    cause = getattr(orig, "__cause__", None)
    code = getattr(cause, "sqlstate", None)
    if isinstance(code, str) and code:
        return code
    return None


def dbapi_exception_handler(request: Request, exc: DBAPIError | Exception) -> Response:
    """Handles database errors that haven't been handled. Most DB errors are server faults (500) but certain
    errors (eg string length constraints) are caused by a client sending data that violates a DB constraint and are
    instead returned as a BadRequest with a generic sep2 ErrorResponse.

    The message is deliberately generic to avoid leaking any internal DB schema details."""
    if not isinstance(exc, DBAPIError):
        return general_exception_handler(request, exc)

    sqlstate = get_dbapi_error_sqlstate(exc)
    message = BAD_REQUEST_SQLSTATES.get(sqlstate) if sqlstate else None
    if message is None:
        return general_exception_handler(request, exc)

    logger.exception(f"{request.path_params} generated DB constraint exception (sqlstate {sqlstate}) {exc}")
    return generate_error_response(HTTPStatus.BAD_REQUEST, message=message)


def general_exception_handler(request: Request, exc: Exception) -> Response:
    """Handles general purpose exceptions that haven't been handled
    through another means"""

    logger.exception(f"{request.path_params} generated exception {exc}")

    # don't leak any internal information about a 500
    return generate_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, message=None)


class LoggedHttpException(HTTPException):
    """This is for all intents and purposes a HTTPException - it will just also utilise the specified
    logger to log the exception too.

    It's a simple way of making the various HTTP Exception handlers more consistent with their logging practices"""

    def __init__(
        self, logger_instance: logging.Logger, exc: Exception | None, status_code: HTTPStatus, detail: str
    ) -> None:
        super().__init__(status_code, detail)

        log_message = f"LoggedHttpException ({int(status_code)}) {status_code}: {detail}"
        if exc is None:
            logger_instance.info(log_message)
        else:
            logger_instance.error(log_message, exc_info=exc)
