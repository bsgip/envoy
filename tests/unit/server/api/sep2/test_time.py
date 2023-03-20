import pytest
from starlette.testclient import TestClient

from server.main import app
from tests.unit.server.resources import TEST_CERTIFICATE_PEM, bs_cert_pem_header


@pytest.mark.asyncio
async def test_get_time_resource(
    mocker,
):
    mocker.patch(
        "server.crud.auth.select_client_ids_using_lfdi",
        return_value={"certificate_id": 1, "aggregator_id": 1},
    )

    with TestClient(app) as client:
        resp = client.get("/tm", headers={bs_cert_pem_header: TEST_CERTIFICATE_PEM})

    assert resp.status_code == 200


def test_invalid_methods():
    with TestClient(app) as client:
        response = client.post(
            "/tm", headers={bs_cert_pem_header: TEST_CERTIFICATE_PEM}
        )
        assert response.status_code == 405

        response = client.put("/tm", headers={bs_cert_pem_header: TEST_CERTIFICATE_PEM})
        assert response.status_code == 405

        response = client.delete(
            "/tm", headers={bs_cert_pem_header: TEST_CERTIFICATE_PEM}
        )
        assert response.status_code == 405
