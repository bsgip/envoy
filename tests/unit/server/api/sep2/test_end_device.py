import pytest
from starlette.testclient import TestClient

from server.main import app
from server.schema.sep2.end_device import EndDeviceListResponse
from tests.unit.server.resources import TEST_CERTIFICATE_PEM, bs_cert_pem_header


@pytest.mark.asyncio
async def test_get_empty_end_device_list(mocker):
    mocker.patch(
        "server.crud.auth.select_client_ids_using_lfdi",
        return_value={"certificate_id": 1, "aggregator_id": 1},
    )
    mocker.patch(
        "server.crud.end_device.select_all_sites_with_aggregator_id",
        return_value=[],
    )

    with TestClient(app) as client:
        resp = client.get("/edev", headers={bs_cert_pem_header: TEST_CERTIFICATE_PEM})

    assert resp.status_code == 200
    assert EndDeviceListResponse.from_xml(resp.content)


@pytest.mark.asyncio
async def test_get_end_device(mocker):
    # TODO
    pass
