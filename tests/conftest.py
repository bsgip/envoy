import glob
import os
import random
import sys

import alembic.config
import pytest
from psycopg import Connection
from pytest_postgresql import factories

from tests.postgres_testing import generate_async_conn_str_from_connection
from tests.unit.jwt import DEFAULT_CLIENT_ID, DEFAULT_ISSUER, DEFAULT_TENANT_ID

# Redefine postgresql fixture if the environment variable, TEST_WITH_DOCKER is True
# The postgresql fixture comes from the pytest-postgresql plugin. See https://pypi.org/project/pytest-postgresql/)
test_with_docker = os.getenv("TEST_WITH_DOCKER", "False").lower() in ("true", "1", "t", "True", "TRUE", "T")
if test_with_docker:
    # The password needs to match the password set in docker-compose.testing.yaml
    # If the dbname table exists, it will raise a DuplicateDatabase error in psycopg
    # from the pytest-postgresql plugin. This happens if we stop a debug session
    # mid-way and thus prevent auto teardown. Fix is to rebuild container for now or drop tables.
    postgresql_in_docker = factories.postgresql_noproc(
        port=5433, dbname=f"envoytestdb_{random.randint(0, sys.maxsize)}", password="adminpass"
    )
    postgresql = factories.postgresql("postgresql_in_docker")


@pytest.fixture
def pg_empty_config(postgresql, request: pytest.FixtureRequest) -> Connection:
    """Sets up the testing DB, applies alembic migrations but does NOT add any entities"""

    # Install the DATABASE_URL before running alembic
    os.environ["DATABASE_URL"] = generate_async_conn_str_from_connection(postgresql)

    pem_marker = request.node.get_closest_marker("cert_header")
    if pem_marker is not None:
        os.environ["CERT_HEADER"] = str(pem_marker.args[0])

    azure_ad_auth_marker = request.node.get_closest_marker("azure_ad_auth")
    if azure_ad_auth_marker is not None:
        os.environ["AZURE_AD_TENANT_ID"] = DEFAULT_TENANT_ID
        os.environ["AZURE_AD_CLIENT_ID"] = DEFAULT_CLIENT_ID
        os.environ["AZURE_AD_VALID_ISSUER"] = DEFAULT_ISSUER
    else:
        os.environ["AZURE_AD_TENANT_ID"] = ""
        os.environ["AZURE_AD_CLIENT_ID"] = ""
        os.environ["AZURE_AD_VALID_ISSUER"] = ""

    # we want alembic to run from the server directory but to revert back afterwards
    cwd = os.getcwd()
    try:
        os.chdir("./src/envoy/server/")

        # Create migrations (if none are there)
        if len(glob.glob("alembic/versions/*.py")) == 0:
            alembicArgs = [
                "--raiseerr",
                "revision",
                "--autogenerate",
                "-m",
                "init",
            ]
            alembic.config.main(argv=alembicArgs)

        # Apply migrations
        alembicArgs = [
            "--raiseerr",
            "upgrade",
            "head",
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
def pg_la_timezone(pg_base_config) -> Connection:
    """Mutates pg_base_config to set all site timezones to Los Angeles time"""

    with open("tests/data/sql/la_timezone.sql") as f:
        base_config_sql = f.read()

    with pg_base_config.cursor() as cursor:
        cursor.execute(base_config_sql)
        pg_base_config.commit()

    yield pg_base_config


@pytest.fixture
def pg_billing_data(pg_base_config) -> Connection:
    """Mutates pg_base_config to include additional billing specific data"""

    with open("tests/data/sql/billing_data.sql") as f:
        billing_data_sql = f.read()

    with pg_base_config.cursor() as cursor:
        cursor.execute(billing_data_sql)
        pg_base_config.commit()

    yield pg_base_config


@pytest.fixture
def anyio_backend():
    """async backends to test against
    see: https://anyio.readthedocs.io/en/stable/testing.html"""
    return "asyncio"
