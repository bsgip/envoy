class BadRequestError(Exception):
    """Raised whenever the incoming client request is malformed / problematic and is an indication
    that a HTTP BadRequest should be returned"""

    message: str

    def __init__(self, message: str) -> None:
        self.message = message


class InternalError(Exception):
    """Raised whenever a client request cannot be served due to an unspecified internal error. This error
    indicates that the client is not at fault."""

    message: str

    def __init__(self, message: str) -> None:
        self.message = message


class UnauthorizedError(Exception):
    """Raised whenever the incoming client request has missing / invalid authorisation credentials"""

    message: str

    def __init__(self, message: str) -> None:
        self.message = message


class ForbiddenError(Exception):
    """Raised whenever the incoming client request has valid authorisation credentials but is trying to access
    a resource they don't have a scoped permissions to access"""

    message: str

    def __init__(self, message: str) -> None:
        self.message = message


class NotFoundError(Exception):
    """Raised whenever the incoming request cannot find the specified resource/entity and is an
    indication that a HTTP NotFound should be returned"""

    message: str

    def __init__(self, message: str) -> None:
        self.message = message


class InvalidMappingError(BadRequestError):
    """Raised when a mapper cannot map an entity due to an error with the supplied data"""

    pass


class InvalidIdError(BadRequestError):
    """Raised when the supplied ID information cannot be parsed into a valid value"""

    pass


class UnableToGenerateIdError(Exception):
    """Raised when either the underlying db or application middleware is unable to generate a sufficiently unique id.
    These errors should typically be treated a 5XX response"""

    pass
