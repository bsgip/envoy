import urllib.parse
from datetime import datetime
from http import HTTPStatus

import pytest
from envoy_schema.server.schema.sep2.time import TimeResponse
from httpx import AsyncClient

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_CERT
from tests.data.certificates.certificate6 import TEST_CERTIFICATE_FINGERPRINT as DEVICE_5_CERT
from tests.data.certificates.certificate8 import TEST_CERTIFICATE_FINGERPRINT as UNREGISTERED_CERT
from tests.integration.integration_server import cert_header
from tests.integration.response import assert_response_header, read_response_body_string


@pytest.fixture
def uri():
    return "/tm"


@pytest.mark.anyio
@pytest.mark.parametrize("cert", [AGG_1_CERT, DEVICE_5_CERT, UNREGISTERED_CERT])
async def test_get_time_resource(client: AsyncClient, uri: str, cert: str):
    """Simple test of a valid get - validates that the response looks like XML"""
    response = await client.get(uri, headers={cert_header: urllib.parse.quote(DEVICE_5_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TimeResponse = TimeResponse.from_xml(body)

    diff = datetime.now().timestamp() - parsed_response.currentTime
    assert diff > 0 and diff < 20, f"Diff between now and the timestamp value is {diff}. Was expected to be small"
    assert parsed_response.quality == 4
