import json
import os
import subprocess
from collections.abc import Generator
from decimal import Decimal

import psycopg
import pytest
from assertical.fixtures.environment import environment_snapshot
from assertical.fixtures.postgres import generate_async_conn_str_from_connection
from psycopg import Connection
from pytest_postgresql.executor import PostgreSQLExecutor
from pytest_postgresql.janitor import DatabaseJanitor

from envoy.server.alembic import upgrade
from tests.integration.conftest import READONLY_USER_KEY_1, READONLY_USER_KEY_2, READONLY_USER_NAME
from tests.unit.jwt import DEFAULT_CLIENT_ID, DEFAULT_DATABASE_RESOURCE_ID, DEFAULT_ISSUER, DEFAULT_TENANT_ID

# Name of the throwaway database used (once per test session) to run the full alembic migration
# chain against so its resulting schema/data can be dumped for pg_migrated_schema_dump
MIGRATED_SCHEMA_DB_NAME = "envoy_test_migrated_schema"

DEFAULT_DOE_IMPORT_ACTIVE_WATTS = Decimal("8200")
DEFAULT_DOE_EXPORT_ACTIVE_WATTS = Decimal("5400")
DEFAULT_DOE_LOAD_ACTIVE_WATTS = Decimal("7200")
DEFAULT_DOE_GENERATION_ACTIVE_WATTS = Decimal("4400")
DEFAULT_DOE_RAMP_RATE_PERCENT_PER_SECOND = 50
DEFAULT_SITE_CONTROL_POW10_ENCODING = -2

TEST_IANA_PEN = 28547  # private enterprise number for the Australian National University - for use in testing


@pytest.fixture
def preserved_environment():
    with environment_snapshot():
        yield


@pytest.fixture(scope="session")
def pg_migrated_schema_dump(postgresql_proc: PostgreSQLExecutor) -> Generator[str, None, None]:
    """Runs ONCE for the entire test session.

    Creates a dedicated (throwaway) database on the shared postgres instance, runs the full chain
    of alembic migrations against it (via upgrade()) and exports the resulting schema - plus any
    data seeded by the migrations themselves (e.g. default SiteControlGroup/SiteDER rows) - as a
    plain SQL dump via pg_dump.

    pg_empty_config applies this dump directly to each test's (already empty) database rather
    than re-running the full alembic migration chain for every single test - this is a LOT
    quicker as alembic has to plan/execute dozens of migrations individually whereas applying a
    flat SQL dump is comparatively instant.
    """

    janitor = DatabaseJanitor(
        user=postgresql_proc.user,
        host=postgresql_proc.host,
        port=postgresql_proc.port,
        version=postgresql_proc.version,
        dbname=MIGRATED_SCHEMA_DB_NAME,
        password=postgresql_proc.password,
    )
    janitor.init()
    try:
        with environment_snapshot():
            migration_conn = psycopg.connect(
                dbname=MIGRATED_SCHEMA_DB_NAME,
                user=postgresql_proc.user,
                password=postgresql_proc.password,
                host=postgresql_proc.host,
                port=postgresql_proc.port,
            )
            try:
                os.environ["DATABASE_URL"] = generate_async_conn_str_from_connection(migration_conn)
                os.environ["IANA_PEN"] = str(TEST_IANA_PEN)

                # This will install all of the alembic migrations - DB is accessed via DATABASE_URL
                upgrade()
            finally:
                migration_conn.close()

        pg_dump_result = subprocess.run(
            [
                "pg_dump",
                "--inserts",  # Emit data as INSERT statements (instead of COPY) so it can be replayed via psycopg
                "--no-owner",
                "--no-privileges",
                "-h",
                str(postgresql_proc.host),
                "-p",
                str(postgresql_proc.port),
                "-U",
                postgresql_proc.user,
                "-d",
                MIGRATED_SCHEMA_DB_NAME,
            ],
            env={**os.environ, "PGPASSWORD": postgresql_proc.password or ""},
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        janitor.drop()

    # pg_dump (PG 18+) wraps its output in psql-only "\restrict"/"\unrestrict" meta-commands that
    # aren't valid SQL and break execution via psycopg - strip them out, they only guard against
    # psql executing arbitrary functions mid-restore which isn't a concern for this test dump.
    dump_sql = "\n".join(
        line
        for line in pg_dump_result.stdout.splitlines()
        if not line.startswith("\\restrict") and not line.startswith("\\unrestrict")
    )

    yield dump_sql


@pytest.fixture
def pg_empty_config(
    preserved_environment, postgresql, pg_migrated_schema_dump: str, request: pytest.FixtureRequest
) -> Generator[Connection, None, None]:
    """Sets up the testing DB, applies alembic migrations but does NOT add any entities"""

    # Install the DATABASE_URL before running alembic
    os.environ["DATABASE_URL"] = generate_async_conn_str_from_connection(postgresql)

    # Load the default TEST_IANA_PEN into the IANA_PEN configuration
    os.environ["IANA_PEN"] = str(TEST_IANA_PEN)

    if "notifications_enabled" in request.fixturenames:
        os.environ["ENABLE_NOTIFICATIONS"] = "True"
        # Poll quickly so the app's in-process notification worker drains the queue promptly during tests
        os.environ["NOTIFICATION_POLL_SECONDS"] = "0.2"

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

    if request.node.get_closest_marker("admin_ro_user"):
        os.environ["READ_ONLY_USER"] = READONLY_USER_NAME
        os.environ["READ_ONLY_KEYS"] = f'["{READONLY_USER_KEY_1}", "{READONLY_USER_KEY_2}"]'

    if request.node.get_closest_marker("disable_device_registration"):
        os.environ["ALLOW_DEVICE_REGISTRATION"] = "False"
    else:
        os.environ["ALLOW_DEVICE_REGISTRATION"] = "True"

    nmi_validation_marker = request.node.get_closest_marker("nmi_validation_enabled")
    if nmi_validation_marker is not None:
        os.environ["NMI_VALIDATION_ENABLED"] = "true"
        os.environ["NMI_VALIDATION_PARTICIPANT_ID"] = nmi_validation_marker.args[0]
    else:
        os.environ["NMI_VALIDATION_ENABLED"] = "false"

    allow_nmi_updates_marker = request.node.get_closest_marker("allow_nmi_updates")
    if allow_nmi_updates_marker is not None:
        os.environ["ALLOW_NMI_UPDATES"] = allow_nmi_updates_marker.args[0]

    exclude_endpoints_marker = request.node.get_closest_marker("exclude_endpoints")
    if exclude_endpoints_marker is not None:
        os.environ["exclude_endpoints"] = json.dumps(exclude_endpoints_marker.args[0])

    # Rather than re-running the full (slow) alembic migration chain against this test's database,
    # apply the schema/data dump exported once per session by pg_migrated_schema_dump - this is
    # functionally equivalent to calling upgrade() but a lot quicker.
    execute_sql_for_connection(postgresql, pg_migrated_schema_dump)

    # pg_dump's preamble resets this connection's search_path to '' (it fully schema-qualifies
    # everything it emits so it doesn't need one) - restore the normal default so any unqualified
    # SQL run against this connection for the rest of the test resolves as expected.
    execute_sql_for_connection(postgresql, "SET search_path TO public")

    yield postgresql


def execute_sql_for_connection(cfg: Connection, sql: str) -> None:
    with cfg.cursor() as cursor:
        cursor.execute(sql)  # type: ignore
        cfg.commit()


def execute_sql_file_for_connection(cfg: Connection, path_to_sql_file: str) -> None:
    with open(path_to_sql_file) as f:
        sql = f.read()
    execute_sql_for_connection(cfg, sql)


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
