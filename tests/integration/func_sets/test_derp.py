import urllib.parse
from datetime import date, datetime, timezone
from http import HTTPStatus
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from envoy.server.schema.sep2.der import DERControlListResponse
from tests.assert_time import assert_datetime_equal
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_PEM
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_2_VALID_PEM
from tests.integration.integration_server import cert_pem_header
from tests.integration.request import build_paging_params
from tests.integration.response import assert_response_header, read_response_body_string


def generate_headers(cert: Any):
    return {cert_pem_header: urllib.parse.quote(cert)}

@pytest.fixture
def agg_1_headers():
    return generate_headers(AGG_1_VALID_PEM)


@pytest.fixture
def uri_derp_list_format():
    return "/derp/{site_id}"


@pytest.fixture
def uri_derp_doe_format():
    return "/derp/{site_id}/doe"


@pytest.fixture
def uri_derc_list_format():
    return "/derp/{site_id}/doe/derc"


@pytest.fixture
def uri_derc_day_list_format():
    return "/derp/{site_id}/doe/derc/{date}"

BRISBANE_TZ = ZoneInfo("Australia/Brisbane")
LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")

@pytest.mark.anyio
@pytest.mark.parametrize("site_id, start, limit, changed_after, cert, expected_total, expected_does", [
    (1, None, 99, None, AGG_1_VALID_PEM, 3, [
        (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 1.11, -1.22),
        (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 2.11, -2.22),
        (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 4.11, -4.22),
        ]),
])
async def test_get_dercontrol_list(client: AsyncClient, uri_derc_list_format: str, cert: str, site_id: int,
                                   start: Optional[int], limit: Optional[int], changed_after: Optional[datetime],
                                   expected_total: int, expected_does: list[tuple[datetime, float, float]]):
    """Tests that the list pagination works correctly"""
    path = uri_derc_list_format.format(site_id=site_id) + build_paging_params(start, limit, changed_after)
    response = await client.get(path, headers=generate_headers(cert))
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    assert parsed_response.results == len(expected_does)
    assert parsed_response.all_ == expected_total
    assert len(parsed_response.DERControl) == len(expected_does)
    for ((expected_start, expected_import, expected_output), control) in zip(expected_does, parsed_response.DERControl):
        assert control.DERControlBase_
        assert control.DERControlBase_.opModImpLimW.value == expected_import
        assert control.DERControlBase_.opModExpLimW.value == expected_output
        assert_datetime_equal(expected_start, control.interval.start)
