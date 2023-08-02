import unittest.mock as mock
from asyncio import Future
from typing import Optional, Union

from httpx import Response
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


class MockedAsyncClient:
    """Looks similar to httpx AsyncClient() but returns a mocked response or raises an error"""

    get_calls: int
    result: Optional[Union[Response, Exception]]
    results_by_uri: dict[str, Union[Response, Exception]]

    def __init__(self, result: Union[Response, Exception, dict]) -> None:
        if isinstance(result, dict):
            self.results_by_uri = result
            self.result = None
        else:
            self.results_by_uri = {}
            self.result = result

        self.get_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    def _raise_or_return(self, result: Union[Response, Exception]) -> Response:
        if isinstance(result, Exception):
            raise result
        elif isinstance(result, Response):
            return result
        else:
            raise Exception(f"Mocking error - unknown type: {type(result)} {result}")

    async def get(self, uri):
        self.get_calls = self.get_calls + 1

        uri_specific_result = self.results_by_uri.get(uri, None)
        if uri_specific_result is not None:
            return self._raise_or_return(uri_specific_result)

        if self.result is None:
            raise Exception(f"Mocking error - no mocked result for {uri}")
        return self._raise_or_return(self.result)
