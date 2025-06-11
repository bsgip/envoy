import json
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient
from envoy.admin.api.site_reading import SiteReadingUri
from tests.integration.response import read_response_body_string
from envoy_schema.admin.schema.site_reading import AdminSiteReadingPageResponse


def _build_site_readings_query_string(start: Optional[int], limit: Optional[int]) -> str:
    query = "?"
    if start is not None:
        query = query + f"&start={start}"
    if limit is not None:
        query = query + f"&limit={limit}"
    return query


@pytest.mark.parametrize(
    "site_id, period_start, period_end, start, limit, expected_status, expected_reading_count, expected_total_count",
    [
        # Happy path - valid site with readings
        (
            1,
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00+00:00",
            None,
            None,
            HTTPStatus.OK,
            5,  # Expected number of readings returned
            5,  # Expected total count
        ),
        # Valid site, no readings in time range
        (
            1,
            "2024-12-01T00:00:00+00:00",
            "2024-12-02T00:00:00+00:00",
            None,
            None,
            HTTPStatus.OK,
            0,
            0,
        ),
        # Non-existent site
        (
            999,
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00+00:00",
            None,
            None,
            HTTPStatus.NOT_FOUND,
            None,
            None,
        ),
        # Pagination test
        (
            1,
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00+00:00",
            1,
            2,
            HTTPStatus.OK,
            2,
            5,
        ),
        # Custom limit
        (
            1,
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00+00:00",
            0,
            3,
            HTTPStatus.OK,
            3,
            5,
        ),
    ],
)
@pytest.mark.anyio
async def test_get_site_readings(
    admin_client_auth: AsyncClient,
    pg_base_config,
    site_id: int,
    period_start: str,
    period_end: str,
    start: Optional[int],
    limit: Optional[int],
    expected_status: HTTPStatus,
    expected_reading_count: Optional[int],
    expected_total_count: Optional[int],
):
    """Test site readings endpoint with various parameters and scenarios."""

    uri = SiteReadingUri.format(
        site_id=site_id, period_start=period_start, period_end=period_end
    ) + _build_site_readings_query_string(start, limit)

    response = await admin_client_auth.get(uri)
    assert response.status_code == expected_status

    if expected_status == HTTPStatus.NOT_FOUND:
        return

    body = read_response_body_string(response)
    assert len(body) > 0
    reading_page: AdminSiteReadingPageResponse = AdminSiteReadingPageResponse(**json.loads(body))

    # Validate response structure
    assert isinstance(reading_page.limit, int)
    assert isinstance(reading_page.total_count, int)
    assert isinstance(reading_page.start, int)
    assert isinstance(reading_page.readings, list)

    # Validate pagination metadata
    assert reading_page.total_count == expected_total_count
    assert len(reading_page.readings) == expected_reading_count
    assert reading_page.start == (start if start is not None else 0)
    assert reading_page.limit == (limit if limit is not None else 1000)

    # Validate all readings are correct type
    assert all([isinstance(r, AdminSiteReadingPageResponse) for r in reading_page.readings])

    # Validate all readings belong to the requested site
    assert all([r.site_id == site_id for r in reading_page.readings])


@pytest.mark.anyio
async def test_get_site_readings_invalid_time_range(admin_client_auth: AsyncClient):
    """Test site readings with invalid time range (start > end)."""

    uri = SiteReadingUri.format(
        site_id=1, period_start="2024-01-02T00:00:00+00:00", period_end="2024-01-01T00:00:00+00:00"  # End before start
    )

    response = await admin_client_auth.get(uri)
    # Expect 400 Bad Request for invalid time range
    assert response.status_code == HTTPStatus.BAD_REQUEST
