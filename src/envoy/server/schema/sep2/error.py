import enum
from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.base import BaseXmlModelWithNS


class ReasonCodeType(enum.IntEnum):
    invalid_request_format = 0
    invalid_request_values = 1
    resource_limit_reached = 2
    conditional_subscription_field_not_supported = 3
    maximum_request_frequency_exceeded = 4

    # Custom values outside sep2 specification
    internal_error = 16384  # Unspecified error due to an issue with some internal logic/system


class ErrorResponse(BaseXmlModelWithNS, tag="Error"):
    """Represents a description of a request error and how the client should respond"""
    maxRetryDuration: Optional[int] = element()  # Contains the number of seconds the client SHOULD wait before retrying
    reasonCode: ReasonCodeType = element()  # Code indicating the reason for failure.

    # These properties sit outside the sep2 definition and are our own custom extensions to provide clients
    # with some QoL improvements
    message: Optional[str] = element()
