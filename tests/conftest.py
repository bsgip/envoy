import glob
import os
import random
import sys
from decimal import Decimal
from typing import Generator

import alembic.config
import pytest
from assertical.fixtures.environment import environment_snapshot
from assertical.fixtures.postgres import generate_async_conn_str_from_connection
from psycopg import Connection
from pytest_postgresql import factories

from tests.integration.conftest import READONLY_USER_KEY_1, READONLY_USER_KEY_2, READONLY_USER_NAME
from tests.unit.jwt import DEFAULT_CLIENT_ID, DEFAULT_DATABASE_RESOURCE_ID, DEFAULT_ISSUER, DEFAULT_TENANT_ID

DEFAULT_DOE_IMPORT_ACTIVE_WATTS = Decimal("8200")
DEFAULT_DOE_EXPORT_ACTIVE_WATTS = Decimal("5400")

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
def preserved_environment():
    with environment_snapshot():
        yield


@pytest.fixture
def pg_empty_config(
    preserved_environment, postgresql, request: pytest.FixtureRequest
) -> Generator[Connection, None, None]:
    """Sets up the testing DB, applies alembic migrations but does NOT add any entities"""

    # Install the DATABASE_URL before running alembic
    os.environ["DATABASE_URL"] = generate_async_conn_str_from_connection(postgresql)

    if "notifications_enabled" in request.fixturenames:
        os.environ["ENABLE_NOTIFICATIONS"] = "True"

    pem_marker = request.node.get_closest_marker("cert_header")
    if pem_marker is not None:
        os.environ["CERT_HEADER"] = str(pem_marker.args[0])

    azure_ad_auth_marker = request.node.get_closest_marker("azure_ad_auth")
    if azure_ad_auth_marker is not None:
        os.environ["AZURE_AD_TENANT_ID"] = DEFAULT_TENANT_ID
        os.environ["AZURE_AD_CLIENT_ID"] = DEFAULT_CLIENT_ID
        os.environ["AZURE_AD_VALID_ISSUER"] = DEFAULT_ISSUER

    azure_ad_db_marker = request.node.get_closest_marker("azure_ad_db")
    if azure_ad_db_marker is not None:
        os.environ["AZURE_AD_DB_RESOURCE_ID"] = DEFAULT_DATABASE_RESOURCE_ID

    azure_ad_db_refresh_secs_marker = request.node.get_closest_marker("azure_ad_db_refresh_secs")
    if azure_ad_db_refresh_secs_marker is not None:
        os.environ["AZURE_AD_DB_REFRESH_SECS"] = str(azure_ad_db_refresh_secs_marker.args[0])

    href_prefix_marker = request.node.get_closest_marker("href_prefix")
    if href_prefix_marker is not None:
        os.environ["HREF_PREFIX"] = str(href_prefix_marker.args[0])

    no_default_doe_marker = request.node.get_closest_marker("no_default_doe")
    if no_default_doe_marker is None:
        os.environ["DEFAULT_DOE_IMPORT_ACTIVE_WATTS"] = str(DEFAULT_DOE_IMPORT_ACTIVE_WATTS)
        os.environ["DEFAULT_DOE_EXPORT_ACTIVE_WATTS"] = str(DEFAULT_DOE_EXPORT_ACTIVE_WATTS)

    if request.node.get_closest_marker("csipv11a_xmlns_optin_middleware"):
        os.environ["INSTALL_CSIP_V11A_OPT_IN_MIDDLEWARE"] = "true"

    if request.node.get_closest_marker("admin_ro_user"):
        os.environ["READ_ONLY_USER"] = READONLY_USER_NAME
        os.environ["READ_ONLY_KEYS"] = f'["{READONLY_USER_KEY_1}", "{READONLY_USER_KEY_2}"]'

    if request.node.get_closest_marker("disable_device_registration"):
        os.environ["ALLOW_DEVICE_REGISTRATION"] = "False"
    else:
        os.environ["ALLOW_DEVICE_REGISTRATION"] = "True"

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


def execute_sql_file_for_connection(cfg: Connection, path_to_sql_file: str) -> None:
    with open(path_to_sql_file) as f:
        sql = f.read()
    with cfg.cursor() as cursor:
        cursor.execute(sql)
        cfg.commit()


@pytest.fixture
def pg_base_config(pg_empty_config: Connection, request: pytest.FixtureRequest) -> Generator[Connection, None, None]:
    """Sets up the testing DB, applies alembic migrations and deploys the "base_config" sql file"""

    execute_sql_file_for_connection(pg_empty_config, "tests/data/sql/base_config.sql")

    if request.node.get_closest_marker("disable_device_registration"):
        # If we are disabling_device_registration - run the "cleanup" script
        execute_sql_file_for_connection(pg_empty_config, "tests/data/sql/remove_device_registrations.sql")

    yield pg_empty_config


@pytest.fixture
def pg_la_timezone(pg_base_config) -> Generator[Connection, None, None]:
    """Mutates pg_base_config to set all site timezones to Los Angeles time"""

    execute_sql_file_for_connection(pg_base_config, "tests/data/sql/la_timezone.sql")

    yield pg_base_config


@pytest.fixture
def pg_additional_does(pg_base_config: Connection) -> Generator[Connection, None, None]:
    """Mutates pg_base_config to include additional DOEs"""

    execute_sql_file_for_connection(pg_base_config, "tests/data/sql/additional_does.sql")

    yield pg_base_config


@pytest.fixture
def pg_billing_data(pg_base_config: Connection) -> Generator[Connection, None, None]:
    """Mutates pg_base_config to include additional billing specific data"""

    execute_sql_file_for_connection(pg_base_config, "tests/data/sql/billing_data.sql")

    yield pg_base_config


@pytest.fixture
def anyio_backend():
    """async backends to test against
    see: https://anyio.readthedocs.io/en/stable/testing.html"""
    return "asyncio"
