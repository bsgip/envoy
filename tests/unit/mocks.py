import unittest.mock as mock
from asyncio import Future, Semaphore, TimeoutError, wait_for
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Union

from httpx import Response
from httpx._types import HeaderTypes, RequestContent
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
    content: Optional[Any] = None


class MockedAsyncClient:
    """Looks similar to httpx AsyncClient() but returns a mocked response or raises an error

    Can be fed either a static result in the form of a Response/Exception or a dictionary keyed by URI that
    will return dynamic results depending on incoming URI

    If fed a list - subsequent calls will work through the list
    """

    logged_requests: list[LoggedRequest]
    get_calls: int
    get_calls_by_uri: dict[str, int]
    post_calls: int
    post_calls_by_uri: dict[str, int]
    result: Optional[Union[Response, Exception, list[Union[Response, Exception]]]]
    results_by_uri: dict[str, Union[Response, Exception, list[Union[Response, Exception]]]]

    request_semaphore: Semaphore

    def __init__(self, result: Union[Response, Exception, dict, list[Union[Response, Exception]]]) -> None:
        self.set_results(result)

    def set_results(self, result: Union[Response, Exception, dict, list[Union[Response, Exception]]]):
        """Re-initialises the behaviour of this mock"""
        if isinstance(result, dict):
            self.results_by_uri = result
            self.result = None
        else:
            self.results_by_uri = {}
            self.result = result

        self.logged_requests = []
        self.get_calls = 0
        self.get_calls_by_uri = {}
        self.post_calls = 0
        self.post_calls_by_uri = {}

        self.request_semaphore = Semaphore(value=0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    def _raise_or_return(self, result: Union[Response, Exception, list[Union[Response, Exception]]]) -> Response:

        self.request_semaphore.release()  # Indicate that we have a request

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

    async def get(self, url: str, headers: Optional[HeaderTypes] = None):
        self.get_calls = self.get_calls + 1
        if url in self.get_calls_by_uri:
            self.get_calls_by_uri[url] = self.get_calls_by_uri[url] + 1
        else:
            self.get_calls_by_uri[url] = 1
        self.logged_requests.append(LoggedRequest(method="GET", uri=url, headers=headers))

        uri_specific_result = self.results_by_uri.get(url, None)
        if uri_specific_result is not None:
            return self._raise_or_return(uri_specific_result)

        if self.result is None:
            raise Exception(f"Mocking error - no mocked result for {url}")
        return self._raise_or_return(self.result)

    async def post(
        self,
        url: str,
        content: Optional[RequestContent] = None,
        json: Optional[Any] = None,
        headers: Optional[HeaderTypes] = None,
    ):
        self.post_calls = self.post_calls + 1
        if url in self.post_calls_by_uri:
            self.post_calls_by_uri[url] = self.post_calls_by_uri[url] + 1
        else:
            self.post_calls_by_uri[url] = 1
        self.logged_requests.append(
            LoggedRequest(method="POST", uri=url, headers=headers, content=content if content is not None else json)
        )

        uri_specific_result = self.results_by_uri.get(url, None)
        if uri_specific_result is not None:
            return self._raise_or_return(uri_specific_result)

        if self.result is None:
            raise Exception(f"Mocking error - no mocked result for {url}")
        return self._raise_or_return(self.result)

    async def wait_for_request(self, timeout_seconds: float) -> bool:
        """Waits for up to timeout_seconds for a GET/POST request to be made to this client. If a request
        has already been made before this function call - it will return immediately.

        Each call to wait_for_request will "consume" one request such that future calls will require
        additional requests to be made before returning

        Returns True if a request was "consumed" or False if the timeout was hit"""
        try:

            await wait_for(self.request_semaphore.acquire(), timeout_seconds)
        except TimeoutError:
            return False

        return True

    async def wait_for_n_requests(self, n: int, timeout_seconds: float) -> bool:
        """Waits for up to timeout_seconds for at least n GET/POST requests to be made to this client. Requests made
        before the wait occurred will count towards n.

        Each call to wait_for_n_requests will "consume" n requests such that future calls will require
        additional requests to be made before returning

        Returns True if n requests were "consumed" or False if the timeout was hit"""
        try:
            remaining_timeout_seconds = timeout_seconds
            for _ in range(n):
                start = datetime.now()
                await wait_for(self.request_semaphore.acquire(), remaining_timeout_seconds)
                remaining_timeout_seconds = remaining_timeout_seconds - (datetime.now() - start).seconds

        except TimeoutError:
            return False

        return True
