import logging
from http import HTTPStatus
from typing import Optional, Union

from envoy_schema.server.schema.sep2.error import ErrorResponse
from envoy_schema.server.schema.sep2.types import ReasonCodeType
from fastapi import HTTPException, Request, Response

from envoy.server.api.response import XmlResponse

logger = logging.getLogger(__name__)


def http_status_code_to_reason_code(status_code: Union[HTTPStatus, int]) -> ReasonCodeType:
    if status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return ReasonCodeType.resource_limit_reached
    elif status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
        return ReasonCodeType.internal_error
    else:
        return ReasonCodeType.invalid_request_format


def generate_error_response(
    status_code: Union[HTTPStatus, int], message: Optional[str] = None, max_retry_duration: Optional[int] = None
) -> Response:
    """Generates an XML response loaded with a sep2 Error object"""
    reason_code = http_status_code_to_reason_code(status_code)

    return XmlResponse(
        status_code=status_code,
        content=ErrorResponse(
            **{"reasonCode": reason_code, "message": message, "maxRetryDuration": max_retry_duration}
        ),
    )


def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Handles specific HTTP exceptions"""

    logger.exception(f"{request.path_params} generated status code {exc.status_code} and exception {exc}")

    return generate_error_response(exc.status_code, message=exc.detail)


def general_exception_handler(request: Request, exc: Exception) -> Response:
    """Handles general purpose exceptions that haven't been handled
    through another means"""

    logger.exception(f"{request.path_params} generated exception {exc}")

    # don't leak any internal information about a 500
    return generate_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, message=None)
