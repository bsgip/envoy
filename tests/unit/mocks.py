import unittest.mock as mock
from asyncio import Future
from dataclasses import dataclass
from typing import Optional, Union

from httpx import Response
from httpx._types import HeaderTypes
from sqlalchemy.ext.asyncio import AsyncSession


def create_mock_session() -> mock.Mock:
    """creates a new fully mocked AsyncSession"""
    return mock.Mock(spec_set=AsyncSession)


def assert_mock_session(mock_session: mock.Mock, committed: bool = False):
    """Asserts a mock AsyncSession was committed or not"""
    if committed:
        mock_session.commit.assert_called_once()
    else:
        mock_session.commit.assert_not_called()


def create_async_result(result):
    """Creates an awaitable result (as a Future) that will return immediately"""
    f = Future()
    f.set_result(result)
    return f


@dataclass
class LoggedRequest:
    """For MockedAsyncClient - keeps a simplified log of outgoing requests"""

    method: str
    uri: str
    headers: Optional[HeaderTypes]


class MockedAsyncClient:
    """Looks similar to httpx AsyncClient() but returns a mocked response or raises an error

    Can be fed either a static result in the form of a Response/Exception or a dictionary keyed by URI that
    will return dynamic results depending on incoming URI

    If fed a list - subsequent calls will work through the list
    """

    logged_requests: list[LoggedRequest]
    get_calls: int
    get_calls_by_uri: dict[str, int]
    result: Optional[Union[Response, Exception, list[Union[Response, Exception]]]]
    results_by_uri: dict[str, Union[Response, Exception, list[Union[Response, Exception]]]]

    def __init__(self, result: Union[Response, Exception, dict, list[Union[Response, Exception]]]) -> None:
        if isinstance(result, dict):
            self.results_by_uri = result
            self.result = None
        else:
            self.results_by_uri = {}
            self.result = result

        self.logged_requests = []
        self.get_calls = 0
        self.get_calls_by_uri = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    def _raise_or_return(self, result: Union[Response, Exception, list[Union[Response, Exception]]]) -> Response:
        if isinstance(result, list):
            if len(result) > 0:
                next_result = result.pop(0)
                return self._raise_or_return(next_result)
            else:
                raise Exception("Mocking error - no more responses/errors in list.")
        elif isinstance(result, Exception):
            raise result
        elif isinstance(result, Response):
            return result
        else:
            raise Exception(f"Mocking error - unknown type: {type(result)} {result}")

    async def get(self, uri: str, headers: Optional[HeaderTypes] = None):
        self.get_calls = self.get_calls + 1
        if uri in self.get_calls_by_uri:
            self.get_calls_by_uri[uri] = self.get_calls_by_uri[uri] + 1
        else:
            self.get_calls_by_uri[uri] = 1
        self.logged_requests.append(LoggedRequest(method="GET", uri=uri, headers=headers))

        uri_specific_result = self.results_by_uri.get(uri, None)
        if uri_specific_result is not None:
            return self._raise_or_return(uri_specific_result)

        if self.result is None:
            raise Exception(f"Mocking error - no mocked result for {uri}")
        return self._raise_or_return(self.result)
