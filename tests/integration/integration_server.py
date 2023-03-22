import os

from fastapi.testclient import TestClient
from psycopg import Connection

from tests.postgres_testing import generate_async_conn_str_from_connection

cert_pem_header = 'x-forwarded-client-cert'  # The "special" header that client certs should reference


def create_test_server(db: Connection) -> TestClient:
    """Returns a TestClient that will utilise the specified db connection (ideally constructed from the test
    db fixtures).
    """
    # We need to set the environment variables before importing the app
    os.environ['DATABASE_URL'] = generate_async_conn_str_from_connection(db)
    from server.main import app
    return TestClient(app)

