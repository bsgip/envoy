import urllib.parse
from datetime import date, datetime, timezone
from http import HTTPStatus
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

import envoy.server.schema.uri as uri
from envoy.server.model.doe import DOE_DECIMAL_PLACES
from envoy.server.schema.sep2.der import (
    DERControlListResponse,
    DERControlResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from tests.assert_time import assert_datetime_equal
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_PEM
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as AGG_2_VALID_PEM
from tests.integration.integration_server import cert_pem_header
from tests.integration.request import build_paging_params
from tests.integration.response import assert_error_response, assert_response_header, read_response_body_string


def generate_headers(cert: Any):
    return {cert_pem_header: urllib.parse.quote(cert)}


@pytest.fixture
def agg_1_headers():
    return generate_headers(AGG_1_VALID_PEM)


@pytest.fixture
def uri_derp_list_format():
    return uri.DERProgramListUri


@pytest.fixture
def uri_derp_doe_format():
    return uri.DERProgramUri


@pytest.fixture
def uri_derc_list_format():
    return uri.DERControlListUri


@pytest.fixture
def uri_derc_day_list_format():
    return uri.DERControlListByDateUri


BRISBANE_TZ = ZoneInfo("Australia/Brisbane")
LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, expected_doe_count",
    [
        (1, 3),
        (2, 1),
        (3, None),  # Belongs to agg 2
        (4, 0),
        (5, None),  # DNE
    ],
)
async def test_get_derprogram_list(
    client: AsyncClient,
    uri_derp_list_format,
    uri_derp_doe_format,
    uri_derc_list_format,
    site_id: int,
    expected_doe_count: Optional[int],
    agg_1_headers,
):
    """Tests getting DERPrograms for various sites and validates access constraints

    Being a virtual entity - we don't go too hard on validating the paging (it'll always
    be a single element or a 404)"""

    # Test a known site
    path = uri_derp_list_format.format(site_id=site_id) + build_paging_params(limit=99)
    response = await client.get(path, headers=agg_1_headers)

    if expected_doe_count is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: DERProgramListResponse = DERProgramListResponse.from_xml(body)
        assert parsed_response.href == uri_derp_list_format.format(site_id=site_id)
        assert parsed_response.all_ == 1
        assert parsed_response.results == 1
        assert len(parsed_response.DERProgram) == 1
        assert parsed_response.DERProgram[0].href == uri_derp_doe_format.format(site_id=site_id, der_program_id="doe")
        assert parsed_response.DERProgram[0].DERControlListLink.all_ == expected_doe_count
        assert parsed_response.DERProgram[0].DERControlListLink.href == uri_derc_list_format.format(
            site_id=site_id, der_program_id="doe"
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, expected_doe_count",
    [
        (1, 3),
        (2, 1),
        (3, None),  # Belongs to agg 2
        (4, 0),
        (5, None),  # DNE
    ],
)
async def get_derprogram_doe(
    client: AsyncClient,
    uri_derp_doe_format,
    uri_derc_list_format,
    site_id: int,
    expected_doe_count: Optional[int],
    agg_1_headers,
):
    """Tests getting DERPrograms for various sites and validates access constraints"""

    # Test a known site
    path = uri_derp_doe_format.format(site_id=site_id, der_program_id="doe")
    response = await client.get(path, headers=agg_1_headers)

    if expected_doe_count is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: DERProgramResponse = DERProgramResponse.from_xml(body)
        assert parsed_response.href == uri_derp_doe_format.format(site_id=site_id, der_program_id="doe")
        assert parsed_response.DERControlListLink.all_ == expected_doe_count
        assert parsed_response.DERControlListLink.href == uri_derc_list_format.format(
            site_id=site_id, der_program_id="doe"
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, start, limit, changed_after, cert, expected_total, expected_does",
    [
        # testing pagination
        (
            1,
            None,
            99,
            None,
            AGG_1_VALID_PEM,
            3,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 111, -122),
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        (
            1,
            None,
            2,
            None,
            AGG_1_VALID_PEM,
            3,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 111, -122),
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
            ],
        ),
        (
            1,
            1,
            99,
            None,
            AGG_1_VALID_PEM,
            3,
            [
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        (
            1,
            2,
            99,
            None,
            AGG_1_VALID_PEM,
            3,
            [
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        # testing filters
        (
            2,
            None,
            99,
            None,
            AGG_1_VALID_PEM,
            1,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 311, -322),
            ],
        ),
        (
            1,
            None,
            99,
            datetime(2022, 5, 6, 11, 22, 32, tzinfo=timezone.utc),
            AGG_1_VALID_PEM,
            3,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 111, -122),
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        (
            1,
            None,
            99,
            datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc),
            AGG_1_VALID_PEM,
            2,
            [
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        (
            1,
            None,
            99,
            datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc),
            AGG_1_VALID_PEM,
            1,
            [
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        # Test empty cases
        (4, None, 99, None, AGG_1_VALID_PEM, 0, []),  # Wrong Site
        (1, 3, 99, None, AGG_1_VALID_PEM, 3, []),  # Big Skip
        (1, None, 0, None, AGG_1_VALID_PEM, 3, []),  # Zero limit
        (1, None, 99, datetime(2022, 5, 6, 14, 22, 34, tzinfo=timezone.utc), AGG_1_VALID_PEM, 0, []),  # changed_after
        (1, None, 99, None, AGG_2_VALID_PEM, 0, []),  # Wrong Aggregator
    ],
)
async def test_get_dercontrol_list(
    client: AsyncClient,
    uri_derc_list_format: str,
    cert: str,
    site_id: int,
    start: Optional[int],
    limit: Optional[int],
    changed_after: Optional[datetime],
    expected_total: int,
    expected_does: list[tuple[datetime, float, float]],
):
    """Tests that the list pagination works correctly for various combinations of start/limit/changed_after"""
    path = uri_derc_list_format.format(site_id=site_id, der_program_id="doe") + build_paging_params(
        start, limit, changed_after
    )
    response = await client.get(path, headers=generate_headers(cert))
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    if not parsed_response.DERControl:
        parsed_response.DERControl = []  # Makes it easier to compare
    assert parsed_response.results == len(expected_does)
    assert parsed_response.all_ == expected_total
    assert len(parsed_response.DERControl) == len(expected_does)
    for (expected_start, expected_import, expected_output), ctrl in zip(expected_does, parsed_response.DERControl):
        control: DERControlResponse = ctrl
        assert control.DERControlBase_
        assert control.DERControlBase_.opModImpLimW.value == expected_import
        assert control.DERControlBase_.opModImpLimW.multiplier == DOE_DECIMAL_PLACES
        assert control.DERControlBase_.opModExpLimW.value == expected_output
        assert control.DERControlBase_.opModExpLimW.multiplier == DOE_DECIMAL_PLACES
        assert_datetime_equal(expected_start, control.interval.start)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, day, start, limit, changed_after, cert, expected_total, expected_does",
    [
        # testing filters
        (
            1,
            date(2022, 5, 7),
            None,
            99,
            None,
            AGG_1_VALID_PEM,
            2,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 111, -122),
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
            ],
        ),
        (
            1,
            date(2022, 5, 8),
            None,
            99,
            None,
            AGG_1_VALID_PEM,
            1,
            [
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        (
            2,
            date(2022, 5, 7),
            None,
            99,
            None,
            AGG_1_VALID_PEM,
            1,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 311, -322),
            ],
        ),
        (
            1,
            date(2022, 5, 7),
            None,
            99,
            datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc),
            AGG_1_VALID_PEM,
            1,
            [
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
            ],
        ),
        # testing pagination
        (
            1,
            date(2022, 5, 7),
            1,
            99,
            None,
            AGG_1_VALID_PEM,
            2,
            [
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
            ],
        ),
        (
            1,
            date(2022, 5, 7),
            None,
            1,
            None,
            AGG_1_VALID_PEM,
            2,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 111, -122),
            ],
        ),
        # Test empty cases
        (4, date(2022, 5, 7), None, 99, None, AGG_1_VALID_PEM, 0, []),  # Wrong Site
        (1, date(2022, 5, 6), None, 99, None, AGG_1_VALID_PEM, 0, []),  # Wrong date
        (1, date(2022, 5, 7), 3, 99, None, AGG_1_VALID_PEM, 2, []),  # Big Skip
        (1, date(2022, 5, 7), None, 0, None, AGG_1_VALID_PEM, 2, []),  # Zero limit
        (1, date(2022, 5, 7), None, 0, datetime(2024, 1, 2), AGG_1_VALID_PEM, 0, []),  # changed_after matches nothing
        (1, date(2022, 5, 7), None, 99, None, AGG_2_VALID_PEM, 0, []),  # Wrong Aggregator
    ],
)
async def test_get_dercontrol_list_day(
    client: AsyncClient,
    uri_derc_day_list_format: str,
    cert: str,
    site_id: int,
    start: Optional[int],
    limit: Optional[int],
    changed_after: Optional[datetime],
    expected_total: int,
    expected_does: list[tuple[datetime, float, float]],
    day: date,
):
    """Tests that the list pagination works correctly for various combinations of start/limit/changed_after"""
    path = uri_derc_day_list_format.format(
        site_id=site_id, der_program_id="doe", date=day.isoformat()
    ) + build_paging_params(start, limit, changed_after)
    response = await client.get(path, headers=generate_headers(cert))
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    if not parsed_response.DERControl:
        parsed_response.DERControl = []  # Makes it easier to compare
    assert parsed_response.results == len(expected_does)
    assert parsed_response.all_ == expected_total
    assert len(parsed_response.DERControl) == len(expected_does)
    for (expected_start, expected_import, expected_output), ctrl in zip(expected_does, parsed_response.DERControl):
        control: DERControlResponse = ctrl
        assert control.DERControlBase_
        assert control.DERControlBase_.opModImpLimW.value == expected_import
        assert control.DERControlBase_.opModImpLimW.multiplier == DOE_DECIMAL_PLACES
        assert control.DERControlBase_.opModExpLimW.value == expected_output
        assert control.DERControlBase_.opModExpLimW.multiplier == DOE_DECIMAL_PLACES
        assert_datetime_equal(expected_start, control.interval.start)
