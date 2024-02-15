from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from psycopg import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def generate_async_conn_str_from_connection(db: Connection) -> str:
    """Utility for extracting a (async) connection string from a postgres connection. This is only really suitable for
    working with a test database - it's not production code"""
    cps = db.pgconn
    return f"postgresql+asyncpg://{cps.user.decode('UTF-8')}:{cps.password.decode('UTF-8')}@{cps.host.decode('UTF-8')}:{cps.port.decode('UTF-8')}/{cps.db.decode('UTF-8')}"


class SingleAsyncEngineState:
    """Represents a single AsyncEngine that can be instantiated by cloning a database Connection"""

    engine: AsyncEngine
    session_maker: sessionmaker[AsyncSession]

    def __init__(self, db: Connection) -> None:
        self.engine = create_async_engine(generate_async_conn_str_from_connection(db))
        self.session_maker = sessionmaker(self.engine, class_=AsyncSession)

    async def dispose(self):
        await self.engine.dispose()


@asynccontextmanager
async def generate_async_session(db: Connection) -> AsyncGenerator[AsyncSession, None]:
    """Generates a temporary AsyncSession for use with a test.

    Callers will be responsible for cleaning up the session"""
    engine_state = SingleAsyncEngineState(db)

    generated_session: Optional[AsyncSession] = None
    try:
        generated_session = engine_state.session_maker()
        yield generated_session
    finally:
        if generated_session is not None:
            await generated_session.close()
        await engine_state.dispose()
