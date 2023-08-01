import unittest.mock as mock
from asyncio import Future

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
