import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient

import envoy.server.schema.uri as uris
from envoy.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from envoy.server.schema.sep2.metering_mirror import MirrorUsagePointListResponse
from envoy.server.schema.sep2.types import DeviceCategory
from tests.assert_time import assert_nowish
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_PEM
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as AGG_2_VALID_PEM
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_PEM as AGG_3_VALID_PEM
from tests.data.fake.generator import generate_class_instance
from tests.integration.integration_server import cert_pem_header
from tests.integration.request import build_paging_params
from tests.integration.response import (
    assert_error_response,
    assert_response_header,
    read_location_header,
    read_response_body_string,
)


@pytest.mark.parametrize(
    "start, changed_after, limit, cert, expected_count, expected_mup_hrefs",
    [
        # Testing start / limit
        (0, None, 99, AGG_1_VALID_PEM, 3, ["/mup/4", "/mup/3", "/mup/1"]),
        (1, None, 99, AGG_1_VALID_PEM, 3, ["/mup/3", "/mup/1"]),
        (2, None, 99, AGG_1_VALID_PEM, 3, ["/mup/1"]),
        (3, None, 99, AGG_1_VALID_PEM, 3, []),
        (0, None, 2, AGG_1_VALID_PEM, 3, ["/mup/4", "/mup/3"]),
        (1, None, 1, AGG_1_VALID_PEM, 3, ["/mup/3"]),
        # Changed time
        (
            0,
            datetime(2022, 5, 6, 11, 22, 30, tzinfo=timezone.utc),
            99,
            AGG_1_VALID_PEM,
            3,
            ["/mup/4", "/mup/3", "/mup/1"],
        ),
        (0, datetime(2022, 5, 6, 11, 22, 35, tzinfo=timezone.utc), 99, AGG_1_VALID_PEM, 2, ["/mup/4", "/mup/3"]),
        (0, datetime(2022, 5, 6, 13, 22, 35, tzinfo=timezone.utc), 99, AGG_1_VALID_PEM, 1, ["/mup/4"]),
        (0, datetime(2022, 5, 6, 14, 22, 35, tzinfo=timezone.utc), 99, AGG_1_VALID_PEM, 0, []),
        (1, datetime(2022, 5, 6, 11, 22, 36, tzinfo=timezone.utc), 2, AGG_1_VALID_PEM, 2, ["/mup/3"]),
        # Changed cert
        (0, None, 99, AGG_2_VALID_PEM, 0, []),
    ],
)
@pytest.mark.anyio
async def test_get_mirror_usage_point_list_pagination(
    client: AsyncClient,
    start: Optional[int],
    changed_after: Optional[datetime],
    limit: Optional[int],
    cert: str,
    expected_count: int,
    expected_mup_hrefs: list[int],
):
    """Simple test of pagination of MUPs for a given aggregator"""
    response = await client.get(
        uris.MirrorUsagePointListUri + build_paging_params(limit=limit, start=start, changed_after=changed_after),
        headers={cert_pem_header: urllib.parse.quote(cert)},
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: MirrorUsagePointListResponse = MirrorUsagePointListResponse.from_xml(body)
    assert parsed_response.all_ == expected_count, f"received body:\n{body}"
    assert parsed_response.results == len(expected_mup_hrefs), f"received body:\n{body}"

    if len(expected_mup_hrefs) > 0:
        assert parsed_response.mirrorUsagePoints, f"received body:\n{body}"
        assert [mup.href for mup in parsed_response.mirrorUsagePoints] == expected_mup_hrefs
    else:
        assert (
            parsed_response.mirrorUsagePoints is None or len(parsed_response.mirrorUsagePoints) == 0
        ), f"received body:\n{body}"
