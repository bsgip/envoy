import json
import os
from decimal import Decimal
from typing import Generator

import pytest
from assertical.fixtures.environment import environment_snapshot
from assertical.fixtures.postgres import generate_async_conn_str_from_connection
from psycopg import Connection

from envoy.server.alembic import upgrade
from tests.integration.conftest import READONLY_USER_KEY_1, READONLY_USER_KEY_2, READONLY_USER_NAME
from tests.unit.jwt import DEFAULT_CLIENT_ID, DEFAULT_DATABASE_RESOURCE_ID, DEFAULT_ISSUER, DEFAULT_TENANT_ID

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


@pytest.fixture
def pg_empty_config(
    preserved_environment, postgresql, request: pytest.FixtureRequest
) -> Generator[Connection, None, None]:
    """Sets up the testing DB, applies alembic migrations but does NOT add any entities"""

    # Install the DATABASE_URL before running alembic
    os.environ["DATABASE_URL"] = generate_async_conn_str_from_connection(postgresql)

    # Load the default TEST_IANA_PEN into the IANA_PEN configuration
    os.environ["IANA_PEN"] = str(TEST_IANA_PEN)

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
        os.environ["USE_GLOBAL_DEFAULT_DOE_FALLBACK"] = "true"
        os.environ["DEFAULT_DOE_IMPORT_ACTIVE_WATTS"] = str(DEFAULT_DOE_IMPORT_ACTIVE_WATTS)
        os.environ["DEFAULT_DOE_EXPORT_ACTIVE_WATTS"] = str(DEFAULT_DOE_EXPORT_ACTIVE_WATTS)
        os.environ["DEFAULT_DOE_LOAD_ACTIVE_WATTS"] = str(DEFAULT_DOE_LOAD_ACTIVE_WATTS)
        os.environ["DEFAULT_DOE_GENERATION_ACTIVE_WATTS"] = str(DEFAULT_DOE_GENERATION_ACTIVE_WATTS)
        os.environ["DEFAULT_DOE_RAMP_RATE_PERCENT_PER_SECOND"] = str(DEFAULT_DOE_RAMP_RATE_PERCENT_PER_SECOND)

    else:
        os.environ["USE_GLOBAL_DEFAULT_DOE_FALLBACK"] = "false"

    if request.node.get_closest_marker("admin_ro_user"):
        os.environ["READ_ONLY_USER"] = READONLY_USER_NAME
        os.environ["READ_ONLY_KEYS"] = f'["{READONLY_USER_KEY_1}", "{READONLY_USER_KEY_2}"]'

    if request.node.get_closest_marker("disable_device_registration"):
        os.environ["ALLOW_DEVICE_REGISTRATION"] = "False"
    else:
        os.environ["ALLOW_DEVICE_REGISTRATION"] = "True"

    nmi_validation_marker = request.node.get_closest_marker("nmi_validation_enabled")
    if nmi_validation_marker is not None:
        os.environ["nmi_validation_enabled"] = "true"
        os.environ["nmi_validation_participant_id"] = nmi_validation_marker.args[0]
    else:
        os.environ["nmi_validation_enabled"] = "false"

    exclude_endpoints_marker = request.node.get_closest_marker("exclude_endpoints")
    if exclude_endpoints_marker is not None:
        os.environ["exclude_endpoints"] = json.dumps(exclude_endpoints_marker.args[0])

    # This will install all of the alembic migrations - DB is accessed from the DATABASE_URL env variable
    upgrade()

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
