from http import HTTPStatus
from urllib.parse import quote

import pytest
from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from httpx import AsyncClient

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as AGG_2_VALID_CERT
from tests.data.certificates.certificate7 import TEST_CERTIFICATE_PEM as DEVICE_REGISTERED_CERT
from tests.data.certificates.certificate8 import TEST_CERTIFICATE_PEM as DEVICE_UNREGISTERED_CERT
from tests.integration.integration_server import cert_header
from tests.integration.response import assert_response_header, read_response_body_string


@pytest.mark.parametrize(
    "cert, edev_count, mup_count",
    [
        (AGG_1_VALID_CERT, 4, 3),  # Agg 1 - 3 edevs + agg edev
        (AGG_2_VALID_CERT, 2, 0),  # Agg 2 - 1 edevs+ agg edev
        (DEVICE_REGISTERED_CERT, 1, 0),  # Device cert - no agg edev
        (DEVICE_UNREGISTERED_CERT, 0, 0),  # Device cert - no agg edev
    ],
)
@pytest.mark.anyio
async def test_get_device_capability(client: AsyncClient, cert: str, edev_count: int, mup_count: int):
    """Simple test of a valid get - validates that the response looks like XML and that the dcap counts are accurate"""
    response = await client.get(uri.DeviceCapabilityUri, headers={cert_header: quote(cert)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DeviceCapabilityResponse = DeviceCapabilityResponse.from_xml(body)
    assert parsed_response.href == uri.DeviceCapabilityUri

    assert parsed_response.TimeLink is not None

    assert parsed_response.EndDeviceListLink is not None
    assert parsed_response.EndDeviceListLink.all_ == edev_count

    assert parsed_response.MirrorUsagePointListLink is not None
    assert parsed_response.MirrorUsagePointListLink.all_ == mup_count
