import urllib.parse
from datetime import datetime
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.server.schema.sep2.end_device import EndDeviceListResponse
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_PEM
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as AGG_2_VALID_PEM
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_PEM as AGG_3_VALID_PEM
from tests.integration.integration_server import cert_pem_header
from tests.integration.response import assert_response_header, read_response_body_string


@pytest.fixture
def edev_list_uri():
    return "/edev"


@pytest.mark.parametrize(
    "aggregator_details",
    [([4444, 2222, 1111], AGG_1_VALID_PEM),
     ([3333], AGG_2_VALID_PEM),
     ([], AGG_3_VALID_PEM)],
)
@pytest.mark.anyio
async def test_get_end_device_list_by_aggregator(client: AsyncClient, edev_list_uri: str, aggregator_details: tuple[list[str], str]):
    """Simple test of a valid get for different aggregator certs - validates that the response looks like XML
    and that it contains the expected end device SFDI's associated with each aggregator"""
    (site_sfdis, cert) = aggregator_details

    response = await client.get(edev_list_uri + '?l=100', headers={cert_pem_header: urllib.parse.quote(cert)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceListResponse = EndDeviceListResponse.from_xml(body)
    assert parsed_response.all_ == len(site_sfdis), f"received body:\n{body}"
    assert parsed_response.result == len(site_sfdis), f"received body:\n{body}"

    if len(site_sfdis) > 0:
        assert parsed_response.EndDevice, f"received body:\n{body}"
        assert len(parsed_response.EndDevice) == len(site_sfdis), f"received body:\n{body}"
        assert [ed.sFDI for ed in parsed_response.EndDevice] == site_sfdis


@pytest.mark.parametrize(
    "aggregator_details",
    [("?l=1", [4444], 3, AGG_1_VALID_PEM),
     ("?l=2", [4444, 2222], 3, AGG_1_VALID_PEM),
     ("?l=2&s=1", [2222, 1111], 3, AGG_1_VALID_PEM),
     ("?l=1&s=1", [2222], 3, AGG_1_VALID_PEM),
     ("?l=1&s=2", [1111], 3, AGG_1_VALID_PEM),
     ("?l=1&s=3", [], 3, AGG_1_VALID_PEM),
     ("?l=2&s=2", [1111], 3, AGG_1_VALID_PEM),

     # add in timestamp filtering
     # This will filter down to Site 2,3,4
     (f"?l=5&a={int(datetime(2022, 2, 3, 5, 0, 0).timestamp())}", [4444, 2222], 2, AGG_1_VALID_PEM),
     (f"?l=5&s=1&a={int(datetime(2022, 2, 3, 5, 0, 0).timestamp())}", [2222], 2, AGG_1_VALID_PEM),

     ("?l=2&s=1", [], 1, AGG_2_VALID_PEM),
     ("?l=2&s=1", [], 0, AGG_3_VALID_PEM),
     ("", [], 0, AGG_3_VALID_PEM)],
)
@pytest.mark.anyio
async def test_get_end_device_list_pagination(client: AsyncClient, edev_list_uri: str, aggregator_details: tuple[str, list[str], int, str]):
    """Tests that pagination variables on the list endpoint are respected"""
    (query_string, site_sfdis, expected_total, cert) = aggregator_details

    response = await client.get(edev_list_uri + query_string, headers={cert_pem_header: urllib.parse.quote(cert)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceListResponse = EndDeviceListResponse.from_xml(body)
    assert parsed_response.all_ == expected_total, f"received body:\n{body}"
    assert parsed_response.result == len(site_sfdis), f"received body:\n{body}"

    if len(site_sfdis) > 0:
        assert parsed_response.EndDevice, f"received body:\n{body}"
        assert len(parsed_response.EndDevice) == len(site_sfdis), f"received body:\n{body}"
        assert [ed.sFDI for ed in parsed_response.EndDevice] == site_sfdis
