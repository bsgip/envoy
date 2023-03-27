import glob
import os

import alembic.config
import pytest
from psycopg import Connection

from tests.postgres_testing import generate_async_conn_str_from_connection


@pytest.fixture
def pg_empty_config(postgresql) -> Connection:
    """Sets up the testing DB, applies alembic migrations but does NOT add any entities"""

    # Install the DATABASE_URL before running alembic
    os.environ['DATABASE_URL'] = generate_async_conn_str_from_connection(postgresql)

    # we want alembic to run from the server directory but to revert back afterwards
    cwd = os.getcwd()
    try:
        os.chdir('./src/envoy/server/')

        # Create migrations (if none are there)
        if len(glob.glob('alembic/versions/*.py')) == 0:
            alembicArgs = [
                '--raiseerr',
                'revision', '--autogenerate', '-m', 'init',
            ]
            alembic.config.main(argv=alembicArgs)

        # Apply migrations
        alembicArgs = [
            '--raiseerr',
            'upgrade', 'head',
        ]
        alembic.config.main(argv=alembicArgs)
    finally:
        os.chdir(cwd)

    yield postgresql


@pytest.fixture
def pg_base_config(pg_empty_config) -> Connection:
    """Sets up the testing DB, applies alembic migrations and deploys the "base_config" sql file"""

    with open("tests/data/sql/base_config.sql") as f:
        base_config_sql = f.read()

    with pg_empty_config.cursor() as cursor:
        cursor.execute(base_config_sql)
        pg_empty_config.commit()

    yield pg_empty_config


@pytest.fixture
def anyio_backend():
    """async backends to test against
    see: https://anyio.readthedocs.io/en/stable/testing.html"""
    return 'asyncio'
