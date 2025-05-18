import asyncio
import urllib.parse
from datetime import datetime, timedelta, timezone
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
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from envoy.server.crud.end_device import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.mapper.csip_aus.doe import DERControlMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from tests.conftest import (
    DEFAULT_DOE_EXPORT_ACTIVE_WATTS,
    DEFAULT_DOE_IMPORT_ACTIVE_WATTS,
    DEFAULT_SITE_CONTROL_POW10_ENCODING,
)
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate6 import TEST_CERTIFICATE_FINGERPRINT as DEVICE_5_CERT
from tests.data.certificates.certificate8 import TEST_CERTIFICATE_FINGERPRINT as UNREGISTERED_CERT
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
def uri_derc_and_list_by_date_format():
    return uri.DERControlUri


@pytest.fixture
def uri_derc_default_control_format():
    return uri.DefaultDERControlUri


@pytest.fixture
def uri_derc_active_control_list_format():
    return uri.ActiveDERControlListUri


@pytest.fixture
def uri_derc_list_format():
    return uri.DERControlListUri


BRISBANE_TZ = ZoneInfo("Australia/Brisbane")
LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, expected_doe_count, expected_status",
    [
        (1, 3, HTTPStatus.OK),
        (2, 1, HTTPStatus.OK),
        (3, None, HTTPStatus.NOT_FOUND),  # Belongs to agg 2
        (4, 0, HTTPStatus.OK),
        (5, None, HTTPStatus.NOT_FOUND),  # Belongs to device cert
        (99, None, HTTPStatus.NOT_FOUND),  # DNE
        (0, None, HTTPStatus.FORBIDDEN),  # Virtual aggregator device cant access DERPs
    ],
)
@freeze_time("2010-01-01")  # This endpoint is sensitive to "now" and won't report on "old" DOEs
async def test_get_derprogram_list(
    client: AsyncClient,
    uri_derp_list_format,
    uri_derp_doe_format,
    uri_derc_list_format,
    site_id: int,
    expected_doe_count: Optional[int],
    expected_status: Optional[HTTPStatus],
    agg_1_headers,
):
    """Tests getting DERPrograms for various sites and validates access constraints

    Being a virtual entity - we don't go too hard on validating the paging (it'll always
    be a single element or a 404)"""

    # Test a known site
    path = uri_derp_list_format.format(site_id=site_id) + build_paging_params(limit=99)
    response = await client.get(path, headers=agg_1_headers)

    if expected_doe_count is None:
        assert_response_header(response, expected_status)
        assert_error_response(response)
    else:
        assert_response_header(response, expected_status)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: DERProgramListResponse = DERProgramListResponse.from_xml(body)
        assert parsed_response.href == uri_derp_list_format.format(site_id=site_id)
        assert parsed_response.all_ == 1
        assert parsed_response.results == 1
        assert len(parsed_response.DERProgram) == 1
        assert parsed_response.DERProgram[0].href == uri_derp_doe_format.format(site_id=site_id, der_program_id=1)
        assert parsed_response.DERProgram[0].DERControlListLink.all_ == expected_doe_count
        assert parsed_response.DERProgram[0].DERControlListLink.href == uri_derc_list_format.format(
            site_id=site_id, der_program_id=1
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, expected_doe_count",
    [
        (1, 3),
        (2, 1),
        (3, None),  # Belongs to agg 2
        (4, 0),
        (5, None),  # Device cert
        (99, None),  # DNE
    ],
)
@freeze_time("2010-01-01")  # This endpoint is sensitive to "now" and won't report on "old" DOEs
async def test_get_derprogram_doe(
    client: AsyncClient,
    uri_derp_doe_format,
    uri_derc_list_format,
    site_id: int,
    expected_doe_count: Optional[int],
    agg_1_headers,
):
    """Tests getting DERPrograms for various sites and validates access constraints"""

    # Test a known site
    path = uri_derp_doe_format.format(site_id=site_id, der_program_id=1)
    response = await client.get(path, headers=agg_1_headers)

    if expected_doe_count is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: DERProgramResponse = DERProgramResponse.from_xml(body)
        assert parsed_response.href == uri_derp_doe_format.format(site_id=site_id, der_program_id=1)
        assert parsed_response.DERControlListLink.all_ == expected_doe_count
        assert parsed_response.DERControlListLink.href == uri_derc_list_format.format(site_id=site_id, der_program_id=1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, start, limit, changed_after, cert, expected_status, expected_total, expected_does",
    [
        # testing pagination
        (
            1,
            None,
            99,
            None,
            AGG_1_VALID_CERT,
            HTTPStatus.OK,
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
            HTTPStatus.OK,
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
            HTTPStatus.OK,
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
            HTTPStatus.OK,
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
            HTTPStatus.OK,
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
            HTTPStatus.OK,
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
            HTTPStatus.OK,
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
            HTTPStatus.OK,
            1,
            [
                (datetime(2022, 5, 8, 1, 2, tzinfo=BRISBANE_TZ), 411, -422),
            ],
        ),
        # Test empty cases
        (4, None, 99, None, AGG_1_VALID_CERT, HTTPStatus.OK, 0, []),  # Wrong Site
        (1, 3, 99, None, AGG_1_VALID_CERT, HTTPStatus.OK, 3, []),  # Big Skip
        (1, None, 0, None, AGG_1_VALID_CERT, HTTPStatus.OK, 3, []),  # Zero limit
        (
            1,
            None,
            99,
            datetime(2022, 5, 6, 14, 22, 34, tzinfo=timezone.utc),
            AGG_1_VALID_CERT,
            HTTPStatus.OK,
            0,
            [],
        ),  # changed_after
        (1, None, 99, None, AGG_2_VALID_CERT, HTTPStatus.OK, 0, []),  # Wrong Aggregator
        (1, None, 99, None, DEVICE_5_CERT, HTTPStatus.FORBIDDEN, 0, []),  # Wrong Aggregator
        (5, None, 99, None, AGG_1_VALID_CERT, HTTPStatus.OK, 0, []),  # Wrong Aggregator
        (5, None, 99, None, UNREGISTERED_CERT, HTTPStatus.FORBIDDEN, 0, []),  # Wrong Aggregator
        (
            0,
            None,
            99,
            None,
            AGG_1_VALID_CERT,
            HTTPStatus.FORBIDDEN,
            0,
            [],
        ),  # No DOEs for virtual edev
        # Note: The order of the does is not guaranteed (duplicate datetime for sites, so this is
        # dependent on order of insertion and currently fragile)
    ],
)
@freeze_time("2010-01-01")  # This endpoint is sensitive to "now" and won't report on "old" DOEs
async def test_get_dercontrol_list(
    client: AsyncClient,
    uri_derc_list_format: str,
    cert: str,
    site_id: int,
    start: Optional[int],
    limit: Optional[int],
    changed_after: Optional[datetime],
    expected_status: HTTPStatus,
    expected_total: int,
    expected_does: list[tuple[datetime, float, float]],
):
    """Tests that the list pagination works correctly for various combinations of start/limit/changed_after"""
    path = uri_derc_list_format.format(site_id=site_id, der_program_id=1) + build_paging_params(
        start, limit, changed_after
    )
    response = await client.get(path, headers=generate_headers(cert))
    assert_response_header(response, expected_status)

    if expected_status != HTTPStatus.OK:
        assert_error_response(response)
    else:
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
            assert control.DERControlBase_.opModImpLimW.multiplier == DEFAULT_SITE_CONTROL_POW10_ENCODING
            assert control.DERControlBase_.opModExpLimW.value == expected_output
            assert control.DERControlBase_.opModExpLimW.multiplier == DEFAULT_SITE_CONTROL_POW10_ENCODING
            assert_datetime_equal(expected_start, control.interval.start)


@pytest.mark.anyio
@freeze_time("2035-01-01")  # Set this far ahead of all DOEs in the database (such that they all count as expired)
async def test_get_dercontrol_list_all_expired(
    client: AsyncClient,
    uri_derc_list_format: str,
):
    """Tests that the DERControl list properly expires DERControls when "now" is after they end"""
    path = uri_derc_list_format.format(site_id=1, der_program_id=1) + build_paging_params(limit=99)
    response = await client.get(path, headers=generate_headers(AGG_1_VALID_CERT))
    assert_response_header(response, HTTPStatus.OK)

    body = read_response_body_string(response)
    assert len(body) > 0

    # yes there are DOEs for site 1 - but they all exist in the past (due to freeze_time)
    parsed_response: DERControlListResponse = DERControlListResponse.from_xml(body)
    assert parsed_response.DERControl is None or parsed_response.DERControl == []
    assert parsed_response.results == 0
    assert parsed_response.all_ == 0


@pytest.mark.anyio
@pytest.mark.no_default_doe
async def test_get_default_doe_not_configured(client: AsyncClient, uri_derc_default_control_format, agg_1_headers):
    """Tests getting the default DOE with no default configured returns 404"""

    # test a known site in base_config that does not have anything set either
    path = uri_derc_default_control_format.format(site_id=2, der_program_id=1)
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)


@pytest.mark.anyio
async def test_get_default_invalid_site_id(client: AsyncClient, uri_derc_default_control_format, agg_1_headers):
    """Tests getting the default DOE with no default configured returns 404"""

    # test trying to fetch a site unavailable to this aggregator
    path = uri_derc_default_control_format.format(site_id=3, der_program_id=1)
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)


@pytest.mark.anyio
async def test_get_fallback_default_doe(client: AsyncClient, uri_derc_default_control_format, agg_1_headers):
    """Tests getting the default DOE"""

    # test a known site
    path = uri_derc_default_control_format.format(site_id=2, der_program_id=1)
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DefaultDERControl = DefaultDERControl.from_xml(body)

    assert (
        parsed_response.DERControlBase_.opModImpLimW.value
        == DERControlMapper.map_to_active_power(
            DEFAULT_DOE_IMPORT_ACTIVE_WATTS, DEFAULT_SITE_CONTROL_POW10_ENCODING
        ).value
    )
    assert (
        parsed_response.DERControlBase_.opModExpLimW.value
        == DERControlMapper.map_to_active_power(
            DEFAULT_DOE_EXPORT_ACTIVE_WATTS, DEFAULT_SITE_CONTROL_POW10_ENCODING
        ).value
    )


@pytest.mark.anyio
async def test_get_site_specific_default_doe(client: AsyncClient, uri_derc_default_control_format, agg_1_headers):
    """Tests getting the default DOE"""

    # test a known site
    path = uri_derc_default_control_format.format(site_id=1, der_program_id=1)
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DefaultDERControl = DefaultDERControl.from_xml(body)

    assert (
        parsed_response.DERControlBase_.opModImpLimW.value
        != DERControlMapper.map_to_active_power(
            DEFAULT_DOE_IMPORT_ACTIVE_WATTS, DEFAULT_SITE_CONTROL_POW10_ENCODING
        ).value
    )
    assert (
        parsed_response.DERControlBase_.opModExpLimW.value
        != DERControlMapper.map_to_active_power(
            DEFAULT_DOE_EXPORT_ACTIVE_WATTS, DEFAULT_SITE_CONTROL_POW10_ENCODING
        ).value
    )


@pytest.mark.anyio
async def test_get_active_doe_nothing_active(client: AsyncClient, uri_derc_active_control_list_format, agg_1_headers):
    """Tests getting the active DOEs when nothing is active returns nothing"""

    # test a known site
    path = uri_derc_active_control_list_format.format(site_id=1, der_program_id=1)
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
        doe_to_edit.end_time = doe_to_edit.start_time + timedelta(seconds=doe_to_edit.duration_seconds)
        await session.commit()

    path = uri_derc_active_control_list_format.format(site_id=1, der_program_id=1)
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
    """Tests getting the active DOEs for an aggregator returns a HTTP 403.

    Note: this test is basically a straight copy/paste from the previous test,
    but tests that even with an active DOE for a site under the aggregator,
    that no DOE is returned. Whether this is the correct behaviour is undefined."""

    # update the DB to move start time to overlap with now
    # Make it overlap for 3 seconds
    async with generate_async_session(pg_base_config) as session:
        stmt = select(DynamicOperatingEnvelope).where(DynamicOperatingEnvelope.dynamic_operating_envelope_id == 2)
        resp = await session.execute(stmt)
        doe_to_edit: DynamicOperatingEnvelope = resp.scalars().one()
        doe_to_edit.duration_seconds = 3
        doe_to_edit.start_time = datetime.now(tz=timezone.utc)
        await session.commit()

    path = uri_derc_active_control_list_format.format(site_id=0, der_program_id=1)
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)

    # Now let the DOE expire
    await asyncio.sleep(3)

    # Now fire the query again - the doe should no longer be active
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, program, doe_id, expected, is_cancelled",
    [
        (1, 1, 1, HTTPStatus.OK, False),  # From the "normal" table
        (1, 1, 19, HTTPStatus.OK, True),  # From the archive (is cancelled)
        (VIRTUAL_END_DEVICE_SITE_ID, 1, 1, HTTPStatus.FORBIDDEN, False),
        (2, 1, 10, HTTPStatus.OK, False),
        (1, 1, 10, HTTPStatus.NOT_FOUND, False),  # Wrong site ID
        (1, 1, 99, HTTPStatus.NOT_FOUND, False),  # Wrong doe ID
        (3, 1, 14, HTTPStatus.NOT_FOUND, False),  # Belongs to site 3 (Under agg 2)
        (1, 99, 1, HTTPStatus.NOT_FOUND, False),  # bad program ID
    ],
)
async def test_get_doe(
    uri_derc_and_list_by_date_format,
    client: AsyncClient,
    pg_additional_does,
    site_id: int,
    program: str,
    doe_id: int,
    expected: HTTPStatus,
    is_cancelled: bool,
    agg_1_headers,
):
    """Tests getting DERPrograms for various sites and validates access constraints"""

    # Test a known site
    path = uri_derc_and_list_by_date_format.format(site_id=site_id, der_program_id=program, derc_id=doe_id)
    response = await client.get(path, headers=agg_1_headers)

    assert_response_header(response, expected)
    if expected != HTTPStatus.OK:
        assert_error_response(response)
    else:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: DERControlResponse = DERControlResponse.from_xml(body)
        assert parsed_response.href == path

        if is_cancelled:
            assert parsed_response.EventStatus_.currentStatus == 2
        else:
            assert parsed_response.EventStatus_.currentStatus == 0
