from datetime import datetime, timezone
import json
from http import HTTPStatus
from typing import Optional
from decimal import Decimal
import pytest
from httpx import AsyncClient
from tests.integration.response import read_response_body_string

from envoy_schema.admin.schema.site_reading import (
    CSIPAusSiteReadingUnit,
    CSIPAusSiteReadingPageResponse,
    CSIPAusSiteReading,
    PhaseEnum,
)
from envoy_schema.admin.schema.uri import CSIPAusSiteReadingUri


def _build_csip_site_readings_query_string(start: Optional[int], limit: Optional[int]) -> str:
    params = []
    if start is not None:
        params.append(f"start={start}")
    if limit is not None:
        params.append(f"limit={limit}")

    return f"?{'&'.join(params)}" if params else ""


@pytest.mark.parametrize(
    "site_id, unit_enum, period_start, period_end, start, limit, expected_reading_count, expected_total_count",
    [
        # Site 1 - compliant reading type ID 1
        (
            1,
            CSIPAusSiteReadingUnit.ACTIVEPOWER,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            None,
            None,
            2,  # 2 readings for type ID 1
            2,
        ),
        # Site 1 - ACTIVEPOWER with pagination
        (
            1,
            CSIPAusSiteReadingUnit.ACTIVEPOWER,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            0,
            1,
            1,  # First page: 1 reading
            2,  # Total: 2 readings
        ),
        # Site 1 - ACTIVEPOWER with pagination (second page)
        (
            1,
            CSIPAusSiteReadingUnit.ACTIVEPOWER,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            1,
            1,
            1,  # Second page: 1 reading
            2,  # Total: 2 readings
        ),
        # Site 1 - ACTIVEPOWER beyond available data
        (
            1,
            CSIPAusSiteReadingUnit.ACTIVEPOWER,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            2,
            1,
            0,  # No more readings
            2,  # Total still 2
        ),
    ],
)
@pytest.mark.anyio
async def test_get_csip_aus_site_readings(
    admin_client_auth: AsyncClient,
    site_id: int,
    unit_enum: CSIPAusSiteReadingUnit,
    period_start: datetime,
    period_end: datetime,
    start: Optional[int],
    limit: Optional[int],
    expected_reading_count: int,
    expected_total_count: int,
):

    uri = CSIPAusSiteReadingUri.format(
        site_id=site_id,
        unit_enum=unit_enum.value,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    ) + _build_csip_site_readings_query_string(start, limit)

    response = await admin_client_auth.get(uri)
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0

    reading_page: CSIPAusSiteReadingPageResponse = CSIPAusSiteReadingPageResponse(**json.loads(body))

    # Validate response structure
    assert isinstance(reading_page.limit, int)
    assert isinstance(reading_page.total_count, int)
    assert isinstance(reading_page.start, int)
    assert isinstance(reading_page.readings, list)
    assert len(reading_page.readings) == expected_reading_count
    assert all([isinstance(r, CSIPAusSiteReading) for r in reading_page.readings])

    # Validate pagination metadata
    assert reading_page.total_count == expected_total_count
    assert reading_page.start == (start if start is not None else 0)
    assert reading_page.limit == (limit if limit is not None else 500)
    assert reading_page.site_id == site_id
    assert reading_page.start_time == period_start
    assert reading_page.end_time == period_end

    # Validate CSIP unit
    assert all([r.csip_aus_unit == unit_enum for r in reading_page.readings])

    # Validate phases
    valid_phases = {PhaseEnum.NA, PhaseEnum.AN, PhaseEnum.BN, PhaseEnum.CN}
    assert all([r.phase in valid_phases for r in reading_page.readings])

    # Validate duration
    assert all([r.duration_seconds > 0 for r in reading_page.readings])


@pytest.mark.parametrize(
    "site_id, unit_enum, period_start, period_end, expected_empty_result",
    [
        # Site 1 - REACTIVEPOWER (none exist in pg_data) - should return empty result
        (
            1,
            CSIPAusSiteReadingUnit.REACTIVEPOWER,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            True,
        ),
        # Site 1 - FREQUENCY (none exist in pg_data) - should return empty result
        (
            1,
            CSIPAusSiteReadingUnit.FREQUENCY,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            True,
        ),
        # Site 1 - VOLTAGE (none exist in pg_data) - should return empty result
        (
            1,
            CSIPAusSiteReadingUnit.VOLTAGE,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            True,
        ),
        # Non-existent site - should return empty result
        (
            999,
            CSIPAusSiteReadingUnit.ACTIVEPOWER,
            datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
            True,
        ),
    ],
)
@pytest.mark.anyio
async def test_get_csip_aus_site_readings_empty_results(
    admin_client_auth: AsyncClient,
    site_id: int,
    unit_enum: CSIPAusSiteReadingUnit,
    period_start: datetime,
    period_end: datetime,
    expected_empty_result: bool,
):
    uri = CSIPAusSiteReadingUri.format(
        site_id=site_id,
        unit_enum=unit_enum.value,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )

    response = await admin_client_auth.get(uri)

    # Always expect OK status
    assert response.status_code == HTTPStatus.OK

    if expected_empty_result:
        body = read_response_body_string(response)
        reading_page = CSIPAusSiteReadingPageResponse(**json.loads(body))

        # Validate empty result structure
        assert reading_page.total_count == 0
        assert len(reading_page.readings) == 0
        assert reading_page.site_id == site_id
        assert reading_page.start_time == period_start
        assert reading_page.end_time == period_end
        assert reading_page.start == 0  # Default start
        assert reading_page.limit == 500  # Default limit


@pytest.mark.anyio
async def test_get_csip_aus_site_readings_detailed_validation(admin_client_auth: AsyncClient):

    uri = CSIPAusSiteReadingUri.format(
        site_id=1,
        unit_enum=CSIPAusSiteReadingUnit.ACTIVEPOWER.value,
        period_start=datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
        period_end=datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
    )

    response = await admin_client_auth.get(uri)
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    reading_page: CSIPAusSiteReadingPageResponse = CSIPAusSiteReadingPageResponse(**json.loads(body))

    # Should have 2 readings for Site 1
    assert len(reading_page.readings) == 2
    assert reading_page.total_count == 2

    for reading in reading_page.readings:
        # Check basic structure
        assert reading.csip_aus_unit == CSIPAusSiteReadingUnit.ACTIVEPOWER
        assert isinstance(reading.value, Decimal)
        assert reading.duration_seconds > 0
        assert reading.reading_start_time is not None


@pytest.mark.anyio
async def test_get_csip_aus_site_readings_invalid_time_range(admin_client_auth: AsyncClient):
    period_start = datetime(2022, 6, 7, 0, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2022, 6, 6, 0, 0, 0, tzinfo=timezone.utc)

    uri = CSIPAusSiteReadingUri.format(
        site_id=1,
        unit_enum=CSIPAusSiteReadingUnit.ACTIVEPOWER.value,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )

    response = await admin_client_auth.get(uri)
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    reading_page = CSIPAusSiteReadingPageResponse(**json.loads(body))

    assert reading_page.total_count == 0
    assert len(reading_page.readings) == 0


@pytest.mark.anyio
async def test_get_csip_aus_site_readings_invalid_unit_enum(admin_client_auth: AsyncClient):
    uri = CSIPAusSiteReadingUri.format(
        site_id=1,
        unit_enum=999,  # Invalid
        period_start=datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
        period_end=datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
    )

    response = await admin_client_auth.get(uri)
    # FastAPI returns 422 for enum validation errors
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_get_csip_aus_site_readings_pagination_consistency(admin_client_auth: AsyncClient):
    """Test that pagination returns consistent results"""
    base_uri = CSIPAusSiteReadingUri.format(
        site_id=1,
        unit_enum=CSIPAusSiteReadingUnit.ACTIVEPOWER.value,
        period_start=datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
        period_end=datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
    )

    # Get all readings at once
    response_all = await admin_client_auth.get(base_uri)
    assert response_all.status_code == HTTPStatus.OK

    body_all = read_response_body_string(response_all)
    page_all = CSIPAusSiteReadingPageResponse(**json.loads(body_all))

    # Get readings page by page
    all_paginated_readings = []
    start = 0
    limit = 1

    while True:
        uri_paginated = base_uri + _build_csip_site_readings_query_string(start, limit)
        response_page = await admin_client_auth.get(uri_paginated)
        assert response_page.status_code == HTTPStatus.OK

        body_page = read_response_body_string(response_page)
        page = CSIPAusSiteReadingPageResponse(**json.loads(body_page))

        if not page.readings:
            break

        all_paginated_readings.extend(page.readings)
        start += limit

    # Compare results
    assert len(page_all.readings) == len(all_paginated_readings)
    assert page_all.total_count == len(all_paginated_readings)

    # Verify reading order is consistent (should be ordered by time_period_start ASC)
    all_times = [r.reading_start_time for r in page_all.readings]
    paginated_times = [r.reading_start_time for r in all_paginated_readings]
    assert all_times == paginated_times


@pytest.mark.anyio
async def test_get_csip_aus_site_readings_response_format(admin_client_auth: AsyncClient):
    uri = CSIPAusSiteReadingUri.format(
        site_id=1,
        unit_enum=CSIPAusSiteReadingUnit.ACTIVEPOWER.value,
        period_start=datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
        period_end=datetime(2022, 6, 30, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
    )

    response = await admin_client_auth.get(uri)
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    reading_page = CSIPAusSiteReadingPageResponse(**json.loads(body))

    # Validate top-level response structure
    required_fields = ["total_count", "limit", "start", "site_id", "start_time", "end_time", "readings"]
    for field in required_fields:
        assert hasattr(reading_page, field), f"Missing required field: {field}"

    # Validate individual reading structure if any readings exist
    if reading_page.readings:
        reading = reading_page.readings[0]
        reading_fields = ["reading_start_time", "duration_seconds", "phase", "value", "csip_aus_unit"]
        for field in reading_fields:
            assert hasattr(reading, field), f"Reading missing required field: {field}"
