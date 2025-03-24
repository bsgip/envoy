import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.log_events import LogEvent, LogEventList
from httpx import AsyncClient
from sqlalchemy import func, insert, select

from envoy.server.model.site import SiteLogEvent
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate6 import TEST_CERTIFICATE_FINGERPRINT as DEVICE_5_CERT
from tests.data.certificates.certificate7 import TEST_CERTIFICATE_FINGERPRINT as DEVICE_6_CERT
from tests.data.certificates.certificate8 import TEST_CERTIFICATE_FINGERPRINT as UNREGISTERED_CERT
from tests.integration.integration_server import cert_header
from tests.integration.request import build_paging_params
from tests.integration.response import (
    assert_error_response,
    assert_response_header,
    read_location_header,
    read_response_body_string,
)


@pytest.fixture
def log_event_list_uri_format():
    return "/edev/{site_id}/lel"


@pytest.fixture
def log_event_uri_format():
    return "/edev/{site_id}/lel/{log_event_id}"


@pytest.mark.parametrize(
    "cert, site_id, log_event_id, expected_details, expected_http_status",
    [
        (AGG_1_VALID_CERT, 1, 1, "log-1", HTTPStatus.OK),
        (AGG_1_VALID_CERT, 1, 2, "log-2", HTTPStatus.OK),
        (AGG_1_VALID_CERT, 2, 3, "log-3", HTTPStatus.OK),
        (AGG_2_VALID_CERT, 3, 4, "log-4", HTTPStatus.OK),
        (AGG_1_VALID_CERT, 1, 5, None, HTTPStatus.OK),
        (DEVICE_5_CERT, 1, 1, None, HTTPStatus.FORBIDDEN),  # Device cert
        (AGG_1_VALID_CERT, 99, 1, None, HTTPStatus.NOT_FOUND),  # site DNE
        (AGG_1_VALID_CERT, 3, 1, None, HTTPStatus.NOT_FOUND),  # site DNE to this agg
        (UNREGISTERED_CERT, 1, 1, None, HTTPStatus.FORBIDDEN),  # Unmatched agg
    ],
)
@pytest.mark.anyio
async def test_get_log_event_for_aggregator(
    client: AsyncClient,
    log_event_uri_format: str,
    cert: str,
    site_id: int,
    log_event_id: int,
    expected_details: Optional[str],
    expected_http_status: HTTPStatus,
):
    """Tests that fetching a specific log event works or fails predictably for an aggregator cert."""
    response = await client.get(
        log_event_uri_format.format(site_id=site_id, log_event_id=log_event_id),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_status)
    if response.status_code == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = LogEvent.from_xml(body)
        assert parsed_response.details == expected_details
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, log_event_id, expected_detail, expected_http_status",
    [
        (DEVICE_5_CERT, 5, 1001, "log-1001", HTTPStatus.OK),  # These get added to the DB at test startup
        (DEVICE_5_CERT, 5, 1002, None, HTTPStatus.OK),  # These get added to the DB at test startup
        (AGG_1_VALID_CERT, 5, 1001, None, HTTPStatus.NOT_FOUND),  # Wrong agg cert
        (DEVICE_6_CERT, 5, 1001, None, HTTPStatus.FORBIDDEN),  # Wrong device cert
        (UNREGISTERED_CERT, 5, 1001, None, HTTPStatus.FORBIDDEN),  # Wrong device cert
    ],
)
@pytest.mark.anyio
async def test_get_log_event_for_device_cert(
    pg_base_config,
    client: AsyncClient,
    log_event_uri_format: str,
    cert: str,
    site_id: int,
    log_event_id: int,
    expected_detail: Optional[str],
    expected_http_status: HTTPStatus,
):
    """Tests that fetching a specific LogEvent works or fails predictably for device certificates."""

    async with generate_async_session(pg_base_config) as session:
        # Add a SiteLogEvent for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(SiteLogEvent).values(
                site_log_event_id=1001,
                site_id=5,
                created_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                details="log-1001",
                extended_data=1002,
                function_set=1,
                log_event_code=2,
                log_event_id=3,
                log_event_pen=4,
                profile_id=0,
            )
        )

        # Add a SiteLogEvent for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(SiteLogEvent).values(
                site_log_event_id=1002,
                site_id=5,
                created_time=datetime(2025, 1, 3, tzinfo=timezone.utc),
                details=None,
                extended_data=1003,
                function_set=2,
                log_event_code=3,
                log_event_id=4,
                log_event_pen=5,
                profile_id=1,
            )
        )

        await session.commit()

    response = await client.get(
        log_event_uri_format.format(site_id=site_id, log_event_id=log_event_id),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_status)
    if expected_http_status == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = LogEvent.from_xml(body)
        assert parsed_response.details == expected_detail
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, start, limit, after, expected_http_response, expected_count, expected_details",
    [
        (AGG_1_VALID_CERT, 0, 0, 99, None, HTTPStatus.OK, 4, [None, "log-3", "log-2", "log-1"]),
        (AGG_1_VALID_CERT, 1, 0, 99, None, HTTPStatus.OK, 3, [None, "log-2", "log-1"]),
        (AGG_1_VALID_CERT, 2, 0, 99, None, HTTPStatus.OK, 1, ["log-3"]),
        (AGG_2_VALID_CERT, 0, 0, 99, None, HTTPStatus.OK, 1, ["log-4"]),
        (AGG_2_VALID_CERT, 3, 0, 99, None, HTTPStatus.OK, 1, ["log-4"]),
        (
            AGG_1_VALID_CERT,
            0,
            0,
            99,
            datetime(2023, 5, 1, 3, 3, 3, tzinfo=timezone.utc),
            HTTPStatus.OK,
            2,
            [None, "log-3"],
        ),  # Pagination
        (AGG_1_VALID_CERT, 0, 1, 2, None, HTTPStatus.OK, 4, ["log-3", "log-2"]),  # Pagination
        (AGG_2_VALID_CERT, 1, 0, 99, None, HTTPStatus.OK, 0, []),  # Wrong aggregator
        (AGG_1_VALID_CERT, 99, 0, 99, None, HTTPStatus.OK, 0, []),  # Wrong site id
        (DEVICE_5_CERT, 1, 0, 99, None, HTTPStatus.FORBIDDEN, None, None),  # Device cert
        (DEVICE_5_CERT, 0, 0, 99, None, HTTPStatus.FORBIDDEN, None, None),  # Device cert
    ],
)
@pytest.mark.anyio
async def test_get_log_event_list_pagination_for_aggregator_cert(
    client: AsyncClient,
    log_event_list_uri_format: str,
    cert: str,
    site_id: int,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_http_response: HTTPStatus,
    expected_count: Optional[int],
    expected_details: Optional[list[Optional[str]]],
):
    """Tests that fetching a response list paginates correctly (or fails predictably)"""
    response = await client.get(
        log_event_list_uri_format.format(site_id=site_id)
        + build_paging_params(start=start, limit=limit, changed_after=after),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_response)
    if expected_http_response == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = LogEventList.from_xml(body)
        assert parsed_response.all_ == expected_count
        assert parsed_response.results == len(expected_details)
        if parsed_response.LogEvent_:
            assert len(parsed_response.LogEvent_) == len(expected_details)
            assert [r.details for r in parsed_response.LogEvent_] == expected_details
        else:
            assert len(expected_details) == 0, "A 0 length array is equivalent to a None LogEvent_ list"
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, start, limit, after, expected_http_response, expected_count, expected_details",
    [
        (DEVICE_5_CERT, 5, 0, 99, None, HTTPStatus.OK, 2, ["log-1002", "log-1001"]),
        (DEVICE_6_CERT, 6, 0, 99, None, HTTPStatus.OK, 0, []),
        (DEVICE_5_CERT, 6, 0, 99, None, HTTPStatus.FORBIDDEN, None, None),  # Wrong site id
    ],
)
@pytest.mark.anyio
async def test_get_log_event_list_pagination_for_device_cert(
    pg_base_config,
    client: AsyncClient,
    log_event_list_uri_format: str,
    cert: str,
    site_id: int,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_http_response: HTTPStatus,
    expected_count: Optional[int],
    expected_details: Optional[list[Optional[str]]],
):
    """Tests that fetching a response list paginates correctly (or fails predictably)"""

    async with generate_async_session(pg_base_config) as session:
        # Add a SiteLogEvent for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(SiteLogEvent).values(
                site_log_event_id=1001,
                site_id=5,
                created_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                details="log-1001",
                extended_data=1002,
                function_set=1,
                log_event_code=2,
                log_event_id=3,
                log_event_pen=4,
                profile_id=0,
            )
        )

        # Add a SiteLogEvent for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(SiteLogEvent).values(
                site_log_event_id=1002,
                site_id=5,
                created_time=datetime(2025, 1, 3, tzinfo=timezone.utc),
                details="log-1002",
                extended_data=1003,
                function_set=2,
                log_event_code=3,
                log_event_id=4,
                log_event_pen=5,
                profile_id=1,
            )
        )

        await session.commit()

    response = await client.get(
        log_event_list_uri_format.format(site_id=site_id)
        + build_paging_params(start=start, limit=limit, changed_after=after),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_response)
    if expected_http_response == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = LogEventList.from_xml(body)
        assert parsed_response.all_ == expected_count
        assert parsed_response.results == len(expected_details)
        if parsed_response.LogEvent_:
            assert len(parsed_response.LogEvent_) == len(expected_details)
            assert [r.details for r in parsed_response.LogEvent_] == expected_details
        else:
            assert len(expected_details) == 0, "A 0 length array is equivalent to a None LogEvent_ list"
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, detail, expected_http_status",
    [
        (AGG_1_VALID_CERT, 1, "new-log", HTTPStatus.CREATED),
        (AGG_1_VALID_CERT, 1, None, HTTPStatus.CREATED),
        (DEVICE_5_CERT, 5, "new-log", HTTPStatus.CREATED),  # Device cert cant talk to another device
        (AGG_2_VALID_CERT, 3, "new-log", HTTPStatus.CREATED),
        (AGG_1_VALID_CERT, 0, None, HTTPStatus.FORBIDDEN),  # Cant post new log events to agg end device
        (AGG_1_VALID_CERT, 3, "new-log", HTTPStatus.NOT_FOUND),  # Site belongs to another agg
        (AGG_1_VALID_CERT, 99, "new-log", HTTPStatus.NOT_FOUND),  # Site DNE
        (DEVICE_5_CERT, 6, "new-log", HTTPStatus.FORBIDDEN),  # Device cert cant talk to another device
    ],
)
@pytest.mark.anyio
async def test_create_log_event(
    pg_base_config,
    client: AsyncClient,
    log_event_list_uri_format: str,
    cert: str,
    site_id: int,
    detail: Optional[str],
    expected_http_status: HTTPStatus,
):
    """Tests the various ways aggregators can send log events to the list endpoint"""
    async with generate_async_session(pg_base_config) as session:
        log_count_before = (await session.execute(select(func.count()).select_from(SiteLogEvent))).scalar_one()

    request_body = generate_class_instance(LogEvent, details=detail)

    response = await client.post(
        log_event_list_uri_format.format(site_id=site_id),
        content=request_body.to_xml(),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    # Created responses don't have a content response
    if expected_http_status == HTTPStatus.CREATED:
        assert_response_header(response, expected_http_status, expected_content_type=None)
    else:
        assert_response_header(response, expected_http_status)

    async with generate_async_session(pg_base_config) as session:
        log_count_after = (await session.execute(select(func.count()).select_from(SiteLogEvent))).scalar_one()

    if expected_http_status == HTTPStatus.CREATED:
        # We should receive a HREF to the created Response. Resolve it to ensure it's valid
        created_href = read_location_header(response)

        response = await client.get(created_href, headers={cert_header: urllib.parse.quote(cert)})
        assert_response_header(response, HTTPStatus.OK)

        parsed_response = LogEvent.from_xml(read_response_body_string(response))
        assert parsed_response.details == detail
        assert_nowish(parsed_response.createdDateTime)

        assert (log_count_before + 1) == log_count_after, "One new LogEvent"
    else:
        assert_error_response(response)
        assert log_count_before == log_count_after, "No new LogEvent"
