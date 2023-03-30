from enum import Enum, auto


# This should be replaced with http.HTTPMethod when this project is ported to Python 3.11
class HTTPMethod(Enum):
    DELETE = auto()
    GET = auto()
    HEAD = auto()
    POST = auto()
    PATCH = auto()
    PUT = auto()
