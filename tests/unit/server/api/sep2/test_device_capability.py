from http import HTTPStatus

import pytest
from starlette.testclient import TestClient

from envoy.server.main import app
from tests.unit.server.resources import TEST_CERTIFICATE_PEM, bs_cert_pem_header


@pytest.fixture
def uri():
    return "/dcap"


@pytest.fixture
def headers():
    return {bs_cert_pem_header: TEST_CERTIFICATE_PEM}


@pytest.mark.asyncio
async def test_get_device_capability(mocker, uri, headers):
    mocker.patch(
        "envoy.server.crud.auth.select_certificate_id_using_lfdi", return_value=1
    )

    with TestClient(app) as client:
        response = client.get(uri, headers=headers)

    assert response.status_code == HTTPStatus.OK


def test_invalid_methods_on_device_capability(uri, headers):
    with TestClient(app) as client:
        response = client.post(uri, headers=headers)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

        response = client.put(uri, headers=headers)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

        response = client.delete(uri, headers=headers)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
