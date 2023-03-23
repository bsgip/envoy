import asyncio
from typing import Generator

import anyio
import pytest
from httpx import AsyncClient
from psycopg import Connection

from tests.postgres_testing import generate_async_conn_str_from_connection

# @pytest.fixture(scope="function")
# def event_loop() -> Generator:
#     """Create an instance of the default event loop for each test case.

#     Failing to have this will cause groups of integration tests to fail when run together"""
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()


@pytest.fixture(scope='function')
async def client(pg_base_config: Connection, event_loop) -> AsyncClient:
    from server.main import app
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


