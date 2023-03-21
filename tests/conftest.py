import os

import alembic.config
import pytest
from psycopg import Connection

from tests.test_db import generate_async_conn_str_from_connection


@pytest.fixture
def pg_empty_config(postgresql) -> Connection:
    """Sets up the testing DB, applies alembic migrations but does NOT add any entities"""
    cwd = os.getcwd()
    print(cwd)
    try:
        os.chdir('./server/')
        alembicArgs = [
            '--raiseerr',
            '-xtest.database.url=' + generate_async_conn_str_from_connection(postgresql),
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
