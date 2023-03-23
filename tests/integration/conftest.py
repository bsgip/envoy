import pytest
from httpx import AsyncClient
from psycopg import Connection


@pytest.fixture
async def client(pg_base_config: Connection):
    """Creates an AsyncClient for a test that is configured to talk to the main server app"""
    from server.main import app
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
