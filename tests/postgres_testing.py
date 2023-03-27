from contextlib import asynccontextmanager
from typing import Optional

from psycopg import Connection
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def generate_async_conn_str_from_connection(db: Connection) -> str:
    """Utility for extracting a (async) connection string from a postgres connection. This is only really suitable for
    working with a test database - it's not production code"""
    cps = db.pgconn
    return f"postgresql+asyncpg://{cps.user.decode('UTF-8')}@{cps.host.decode('UTF-8')}:{cps.port.decode('UTF-8')}/{cps.db.decode('UTF-8')}"


@asynccontextmanager
async def generate_async_session(db: Connection) -> AsyncSession:
    """Generates a temporary AsyncSession for use with a test.

    Callers will be responsible for cleaning up the session"""
    engine = create_async_engine(generate_async_conn_str_from_connection(db))
    generated_session: Optional[AsyncSession] = None
    try:
        Session = sessionmaker(engine, class_=AsyncSession)
        generated_session = Session()
        yield generated_session
    finally:
        if generated_session is not None:
            await generated_session.close()
        await engine.dispose()
