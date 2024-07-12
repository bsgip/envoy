import asyncio
import urllib.parse
from datetime import date, datetime, timezone
from http import HTTPStatus
from typing import Any, Optional
from zoneinfo import ZoneInfo

import envoy_schema.server.schema.uri as uri
import pytest
from assertical.asserts.time import assert_datetime_equal
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.der import (
    DefaultDERControl,
    DERControlListResponse,
    DERControlResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from httpx import AsyncClient
from sqlalchemy import select

from envoy.server.mapper.csip_aus.doe import DERControlMapper
from envoy.server.model.doe import DOE_DECIMAL_PLACES, DynamicOperatingEnvelope
from tests.conftest import DEFAULT_DOE_EXPORT_ACTIVE_WATTS, DEFAULT_DOE_IMPORT_ACTIVE_WATTS
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.integration.integration_server import cert_header
from tests.integration.request import build_paging_params
from tests.integration.response import assert_error_response, assert_response_header, read_response_body_string


def generate_headers(cert: Any):
    return {cert_header: urllib.parse.quote(cert)}


@pytest.fixture
def agg_1_headers():
    return generate_headers(AGG_1_VALID_CERT)


@pytest.fixture
def uri_derp_list_format():
    return uri.DERProgramListUri


@pytest.fixture
def uri_derp_doe_format():
    return uri.DERProgramUri


@pytest.fixture
def uri_derc_default_control_format():
    return uri.DefaultDERControlUri


@pytest.fixture
def uri_derc_active_control_list_format():
    return uri.ActiveDERControlListUri


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
        (0, 4),  # Virtual aggregator device should return all for sites 1 and 2
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
            1,
            [
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        # Test empty cases
        (4, None, 99, None, AGG_1_VALID_CERT, 0, []),  # Wrong Site
        (1, 3, 99, None, AGG_1_VALID_CERT, 3, []),  # Big Skip
        (1, None, 0, None, AGG_1_VALID_CERT, 3, []),  # Zero limit
        (1, None, 99, datetime(2022, 5, 6, 14, 22, 34, tzinfo=timezone.utc), AGG_1_VALID_CERT, 0, []),  # changed_after
        (1, None, 99, None, AGG_2_VALID_CERT, 0, []),  # Wrong Aggregator
        (
            0,
            None,
            99,
            None,
            AGG_1_VALID_CERT,
            4,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 311, -322),
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 111, -122),
                (datetime(2022, 5, 7, 3, 4, tzinfo=BRISBANE_TZ), 211, -222),
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),  # DERControls for aggregator retrieves all site DERControls for aggregator
        # Note: The order of the does is not guaranteed (duplicate datetime for sites, so this is
        # dependent on order of insertion and currently fragile)
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
    assert path.startswith(parsed_response.href), "The derc href should be included in the response"
    assert parsed_response.results == len(expected_does)
    assert parsed_response.all_ == expected_total
    assert len(parsed_response.DERControl) == len(expected_does)
    for (expected_start, expected_import, expected_output), ctrl in zip(expected_does, parsed_response.DERControl):
        control: DERControlResponse = ctrl
        assert control.DERControlBase_
        assert control.DERControlBase_.opModImpLimW.value == expected_import
        assert control.DERControlBase_.opModImpLimW.multiplier == -DOE_DECIMAL_PLACES
        assert control.DERControlBase_.opModExpLimW.value == expected_output
        assert control.DERControlBase_.opModExpLimW.multiplier == -DOE_DECIMAL_PLACES
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
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
            AGG_1_VALID_CERT,
            2,
            [
                (datetime(2022, 5, 7, 1, 2, tzinfo=BRISBANE_TZ), 111, -122),
            ],
        ),
        # Test empty cases
        (4, date(2022, 5, 7), None, 99, None, AGG_1_VALID_CERT, 0, []),  # Wrong Site
        (1, date(2022, 5, 6), None, 99, None, AGG_1_VALID_CERT, 0, []),  # Wrong date
        (1, date(2022, 5, 7), 3, 99, None, AGG_1_VALID_CERT, 2, []),  # Big Skip
        (1, date(2022, 5, 7), None, 0, None, AGG_1_VALID_CERT, 2, []),  # Zero limit
        (1, date(2022, 5, 7), None, 0, datetime(2024, 1, 2), AGG_1_VALID_CERT, 0, []),  # changed_after matches nothing
        (1, date(2022, 5, 7), None, 99, None, AGG_2_VALID_CERT, 0, []),  # Wrong Aggregator
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
    assert path.startswith(parsed_response.href), "The derc href should be included in the response"
    assert parsed_response.results == len(expected_does)
    assert parsed_response.all_ == expected_total
    assert len(parsed_response.DERControl) == len(expected_does)
    for (expected_start, expected_import, expected_output), ctrl in zip(expected_does, parsed_response.DERControl):
        control: DERControlResponse = ctrl
        assert control.DERControlBase_
        assert control.DERControlBase_.opModImpLimW.value == expected_import
        assert control.DERControlBase_.opModImpLimW.multiplier == -DOE_DECIMAL_PLACES
        assert control.DERControlBase_.opModExpLimW.value == expected_output
        assert control.DERControlBase_.opModExpLimW.multiplier == -DOE_DECIMAL_PLACES
        assert_datetime_equal(expected_start, control.interval.start)


@pytest.mark.anyio
@pytest.mark.no_default_doe
async def test_get_default_doe_not_configured(client: AsyncClient, uri_derc_default_control_format, agg_1_headers):
    """Tests getting the default DOE with no default configured returns 404"""

    # test a known site
    path = uri_derc_default_control_format.format(site_id=1, der_program_id="doe")
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)


@pytest.mark.anyio
async def test_get_default_invalid_site_id(client: AsyncClient, uri_derc_default_control_format, agg_1_headers):
    """Tests getting the default DOE with no default configured returns 404"""

    # test trying to fetch a site unavailable to this aggregator
    path = uri_derc_default_control_format.format(site_id=3, der_program_id="doe")
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)


@pytest.mark.anyio
async def test_get_default_doe(client: AsyncClient, uri_derc_default_control_format, agg_1_headers):
    """Tests getting the default DOE"""

    # test a known site
    path = uri_derc_default_control_format.format(site_id=1, der_program_id="doe")
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DefaultDERControl = DefaultDERControl.from_xml(body)

    assert (
        parsed_response.DERControlBase_.opModImpLimW.value
        == DERControlMapper.map_to_active_power(DEFAULT_DOE_IMPORT_ACTIVE_WATTS).value
    )
    assert (
        parsed_response.DERControlBase_.opModExpLimW.value
        == DERControlMapper.map_to_active_power(DEFAULT_DOE_EXPORT_ACTIVE_WATTS).value
    )


@pytest.mark.anyio
async def test_get_active_doe_nothing_active(client: AsyncClient, uri_derc_active_control_list_format, agg_1_headers):
    """Tests getting the active DOEs when nothing is active returns nothing"""

    # test a known site
    path = uri_derc_active_control_list_format.format(site_id=1, der_program_id="doe")
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    assert parsed_response.href == path, "The active doe href should be included in the response"
    assert parsed_response.all_ == 0
    assert parsed_response.DERControl is None or len(parsed_response.DERControl) == 0


@pytest.mark.anyio
async def test_get_active_doe(client: AsyncClient, pg_base_config, uri_derc_active_control_list_format, agg_1_headers):
    """Tests getting the active DOEs after the DOEs have been tweaked to align with datetime.now()"""

    # update the DB to move start time to overlap with now
    # Make it overlap for 3 seconds
    async with generate_async_session(pg_base_config) as session:
        stmt = select(DynamicOperatingEnvelope).where(DynamicOperatingEnvelope.dynamic_operating_envelope_id == 2)
        resp = await session.execute(stmt)
        doe_to_edit: DynamicOperatingEnvelope = resp.scalars().one()
        doe_to_edit.duration_seconds = 3
        doe_to_edit.start_time = datetime.now(tz=timezone.utc)
        await session.commit()

    path = uri_derc_active_control_list_format.format(site_id=1, der_program_id="doe")
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    assert parsed_response.href == path, "The active doe href should be included in the response"
    assert parsed_response.all_ == 1
    assert len(parsed_response.DERControl) == 1

    parsed_response.DERControl[0].DERControlBase_.opModImpLimW.value == 211
    parsed_response.DERControl[0].DERControlBase_.opModExpLimW.value == 212

    # Now let the DOE expire
    await asyncio.sleep(3)

    # Now fire the query again - the doe should no longer be active
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    assert parsed_response.href == path, "The active doe href should be included in the response"
    assert parsed_response.all_ == 0
    assert parsed_response.DERControl is None or len(parsed_response.DERControl) == 0


@pytest.mark.anyio
async def test_get_active_doe_for_aggregator(
    client: AsyncClient, pg_base_config, uri_derc_active_control_list_format, agg_1_headers
):
    """Tests getting the active DOEs for an aggregator returns an empty list.
    Note: this test is basically a straight copy/paste from the previous test,
    but tests that even with an active DOE for a site under the aggregator,
    that no DOE is returned. Whether this is the correct behaviour is undefined,
    but arguably is more consistent than returning a 404."""

    # update the DB to move start time to overlap with now
    # Make it overlap for 3 seconds
    async with generate_async_session(pg_base_config) as session:
        stmt = select(DynamicOperatingEnvelope).where(DynamicOperatingEnvelope.dynamic_operating_envelope_id == 2)
        resp = await session.execute(stmt)
        doe_to_edit: DynamicOperatingEnvelope = resp.scalars().one()
        doe_to_edit.duration_seconds = 3
        doe_to_edit.start_time = datetime.now(tz=timezone.utc)
        await session.commit()

    path = uri_derc_active_control_list_format.format(site_id=0, der_program_id="doe")
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    assert parsed_response.href == path, "The active doe href should be included in the response"
    assert parsed_response.all_ == 0
    assert parsed_response.DERControl is None or len(parsed_response.DERControl) == 0

    # Now let the DOE expire
    await asyncio.sleep(3)

    # Now fire the query again - the doe should no longer be active
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    assert parsed_response.href == path, "The active doe href should be included in the response"
    assert parsed_response.all_ == 0
    assert parsed_response.DERControl is None or len(parsed_response.DERControl) == 0
