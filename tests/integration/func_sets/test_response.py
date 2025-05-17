import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.response import (
    DERControlResponse,
    PriceResponse,
    Response,
    ResponseListResponse,
    ResponseSet,
    ResponseSetList,
    ResponseType,
)
from httpx import AsyncClient
from sqlalchemy import func, insert, select

from envoy.server.mapper.constants import PricingReadingType, ResponseSetType
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.mapper.sep2.response import response_set_type_to_href
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.response import DynamicOperatingEnvelopeResponse, TariffGeneratedRateResponse
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import BaseRequestScope
from tests.conftest import TEST_IANA_PEN
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

DOE_HREF = response_set_type_to_href(ResponseSetType.SITE_CONTROLS)  # Shorthand for brevity
RATE_HREF = response_set_type_to_href(ResponseSetType.TARIFF_GENERATED_RATES)  # Shorthand for brevity
TEST_SCOPE = generate_class_instance(BaseRequestScope, href_prefix=None, iana_pen=TEST_IANA_PEN)


@pytest.fixture
def response_set_uri_format():
    return "/edev/{site_id}/rsps/{response_list_id}"


@pytest.fixture
def response_set_list_uri_format():
    return "/edev/{site_id}/rsps"


@pytest.fixture
def response_list_uri_format():
    return "/edev/{site_id}/rsps/{response_list_id}/rsp"


@pytest.fixture
def response_uri_format():
    return "/edev/{site_id}/rsps/{response_list_id}/rsp/{response_id}"


@pytest.mark.parametrize(
    "response_set_id, exists",
    [
        (DOE_HREF, True),
        (RATE_HREF, True),
        ("foobar", False),
    ],
)
@pytest.mark.anyio
async def test_get_response_set(client: AsyncClient, response_set_uri_format: str, response_set_id: str, exists: bool):
    """Tests that the response sets can be fetched individually and return valid sep2 XML"""
    response = await client.get(
        response_set_uri_format.format(site_id=1, response_list_id=response_set_id),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )

    if exists:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = ResponseSet.from_xml(body)
        assert parsed_response.ResponseListLink is not None
        assert parsed_response.ResponseListLink.href
    else:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)


@pytest.mark.parametrize(
    "start, limit, expected_count",
    [
        (None, None, 1),  # Default limit is 1
        (0, 99, len(ResponseSetType)),
        (0, None, 1),  # Default limit is 1
        (0, 0, 0),
        (99, 99, 0),
        (1, 99, len(ResponseSetType) - 1),
        (0, 1, 1),
        (None, 1, 1),
    ],
)
@pytest.mark.anyio
async def test_get_response_set_list(
    client: AsyncClient,
    response_set_list_uri_format: str,
    start: Optional[int],
    limit: Optional[int],
    expected_count: int,
):
    """Tests that the response set list can be paginated through"""
    response = await client.get(
        response_set_list_uri_format.format(site_id=1) + build_paging_params(limit=limit, start=start),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response = ResponseSetList.from_xml(body)

    assert parsed_response.results == expected_count
    assert parsed_response.all_ == len(ResponseSetType)

    if parsed_response.ResponseSet_ is None:
        assert expected_count == 0
    else:
        assert len(parsed_response.ResponseSet_) == expected_count
        set_link_hrefs = [e.href for e in parsed_response.ResponseSet_]
        list_link_hrefs = [e.ResponseListLink.href for e in parsed_response.ResponseSet_]
        all_hrefs = set_link_hrefs + list_link_hrefs
        assert len(all_hrefs) == len(set(all_hrefs)), "Every href should be unique"


@pytest.mark.parametrize(
    "cert, site_id, response_set_id, response_id, expected_status, expected_response_type, expected_http_status",
    [
        (AGG_1_VALID_CERT, 1, RATE_HREF, 1, 1, PriceResponse, HTTPStatus.OK),
        (AGG_1_VALID_CERT, 0, RATE_HREF, 1, 1, PriceResponse, HTTPStatus.OK),
        (AGG_1_VALID_CERT, 1, DOE_HREF, 1, 3, DERControlResponse, HTTPStatus.OK),
        (AGG_1_VALID_CERT, 0, DOE_HREF, 1, 3, DERControlResponse, HTTPStatus.OK),
        (AGG_1_VALID_CERT, 1, RATE_HREF, 2, None, PriceResponse, HTTPStatus.OK),
        (AGG_1_VALID_CERT, 1, DOE_HREF, 2, None, DERControlResponse, HTTPStatus.OK),
        (DEVICE_5_CERT, 1, DOE_HREF, 1, None, None, HTTPStatus.FORBIDDEN),  # Not aggregator cert
        (AGG_2_VALID_CERT, 1, DOE_HREF, 1, None, None, HTTPStatus.NOT_FOUND),  # Wrong Aggregator
        (AGG_1_VALID_CERT, 2, DOE_HREF, 1, None, None, HTTPStatus.NOT_FOUND),  # Wrong Site ID
        (AGG_1_VALID_CERT, 1, "foobar", 1, None, None, HTTPStatus.NOT_FOUND),  # Wrong set id
        (AGG_1_VALID_CERT, 1, DOE_HREF, 99, None, None, HTTPStatus.NOT_FOUND),  # Wrong id
    ],
)
@pytest.mark.anyio
async def test_get_response_for_aggregator(
    client: AsyncClient,
    response_uri_format: str,
    cert: str,
    site_id: int,
    response_set_id: str,
    response_id: int,
    expected_status: Optional[ResponseType],
    expected_response_type: Optional[type[Response]],
    expected_http_status: HTTPStatus,
):
    """Tests that fetching a specific response works or fails predictably for an aggregator cert.

    if expected_response_type is None - A failure is expected"""
    response = await client.get(
        response_uri_format.format(site_id=site_id, response_list_id=response_set_id, response_id=response_id),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_status)
    if expected_response_type:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = expected_response_type.from_xml(body)
        assert parsed_response.status == expected_status
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, response_set_id, response_id, expected_response_type, expected_status, expected_http_status",
    [
        (
            DEVICE_5_CERT,
            5,
            DOE_HREF,
            1001,
            DERControlResponse,
            7,
            HTTPStatus.OK,
        ),  # These get added to the DB at test startup
        (
            DEVICE_5_CERT,
            5,
            RATE_HREF,
            1002,
            PriceResponse,
            8,
            HTTPStatus.OK,
        ),  # These get added to the DB at test startup
        (AGG_1_VALID_CERT, 5, DOE_HREF, 1001, None, None, HTTPStatus.NOT_FOUND),  # Wrong agg cert
        (DEVICE_6_CERT, 5, DOE_HREF, 1001, None, None, HTTPStatus.FORBIDDEN),  # Wrong device cert
        (UNREGISTERED_CERT, 5, DOE_HREF, 1001, None, None, HTTPStatus.FORBIDDEN),  # Wrong device cert
        (DEVICE_5_CERT, 5, "foobar", 1001, None, None, HTTPStatus.NOT_FOUND),  # Wrong set id
        (DEVICE_5_CERT, 5, DOE_HREF, 99, None, None, HTTPStatus.NOT_FOUND),  # Wrong set id
    ],
)
@pytest.mark.anyio
async def test_get_response_for_device_cert(
    pg_base_config,
    client: AsyncClient,
    response_uri_format: str,
    cert: str,
    site_id: int,
    response_set_id: str,
    response_id: int,
    expected_response_type: Optional[type[Response]],
    expected_status: Optional[ResponseType],
    expected_http_status: HTTPStatus,
):
    """Tests that fetching a specific response works or fails predictably for device certificates.

    If expected_response_type is None - a failure is expected"""

    async with generate_async_session(pg_base_config) as session:
        # Add a DOE for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(DynamicOperatingEnvelope).values(
                dynamic_operating_envelope_id=101,
                site_control_group_id=1,
                site_id=5,
                calculation_log_id=None,
                changed_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                start_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                duration_seconds=300,
                end_time=datetime(2025, 1, 2, 0, 5, 0, tzinfo=timezone.utc),
                import_limit_active_watts=100,
                export_limit_watts=200,
            )
        )

        # Add a rate for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(TariffGeneratedRate).values(
                tariff_generated_rate_id=102,
                tariff_id=1,
                site_id=5,
                calculation_log_id=None,
                changed_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                start_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                duration_seconds=300,
                import_active_price=101,
                export_active_price=202,
                import_reactive_price=303,
                export_reactive_price=404,
            )
        )

        # Add a doe response for site 5 (device cert)
        await session.execute(
            insert(DynamicOperatingEnvelopeResponse).values(
                dynamic_operating_envelope_response_id=1001,
                dynamic_operating_envelope_id=101,
                site_id=5,
                response_type=7,
            )
        )

        # Add a rate response for site 5 (device cert)
        await session.execute(
            insert(TariffGeneratedRateResponse).values(
                tariff_generated_rate_response_id=1002,
                tariff_generated_rate_id=102,
                site_id=5,
                pricing_reading_type=PricingReadingType.IMPORT_ACTIVE_POWER_KWH,
                response_type=8,
            )
        )

        await session.commit()

    response = await client.get(
        response_uri_format.format(site_id=site_id, response_list_id=response_set_id, response_id=response_id),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_status)
    if expected_response_type:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = expected_response_type.from_xml(body)
        assert parsed_response.status == expected_status
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, response_set_id, start, limit, after, expected_http_response, expected_count, expected_statuses",
    [
        (AGG_1_VALID_CERT, 0, RATE_HREF, 0, 99, None, HTTPStatus.OK, 3, [2, None, 1]),
        (AGG_1_VALID_CERT, 1, RATE_HREF, 0, 99, None, HTTPStatus.OK, 2, [None, 1]),
        (AGG_1_VALID_CERT, 2, RATE_HREF, 0, 99, None, HTTPStatus.OK, 1, [2]),
        (AGG_1_VALID_CERT, 0, DOE_HREF, 0, 99, None, HTTPStatus.OK, 3, [4, None, 3]),
        (AGG_1_VALID_CERT, 1, DOE_HREF, 0, 99, None, HTTPStatus.OK, 2, [None, 3]),
        (AGG_1_VALID_CERT, 2, DOE_HREF, 0, 99, None, HTTPStatus.OK, 1, [4]),
        (AGG_1_VALID_CERT, 0, RATE_HREF, 0, 99, None, HTTPStatus.OK, 3, [2, None, 1]),
        (AGG_1_VALID_CERT, 0, RATE_HREF, None, None, None, HTTPStatus.OK, 3, [2]),  # Limit default is 1
        (AGG_1_VALID_CERT, 0, RATE_HREF, 1, 99, None, HTTPStatus.OK, 3, [None, 1]),
        (AGG_1_VALID_CERT, 0, RATE_HREF, 2, 1, None, HTTPStatus.OK, 3, [1]),
        (
            AGG_1_VALID_CERT,
            0,
            RATE_HREF,
            0,
            99,
            datetime(2022, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            HTTPStatus.OK,
            2,
            [2, None],
        ),
        (
            AGG_1_VALID_CERT,
            0,
            RATE_HREF,
            1,
            99,
            datetime(2022, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            HTTPStatus.OK,
            2,
            [None],
        ),
        (AGG_2_VALID_CERT, 1, DOE_HREF, 0, 99, None, HTTPStatus.OK, 0, []),  # Bad Agg ID
        (DEVICE_5_CERT, 1, DOE_HREF, 0, 99, None, HTTPStatus.FORBIDDEN, None, None),  # Bad device cert
        (AGG_1_VALID_CERT, 3, DOE_HREF, 0, 99, None, HTTPStatus.OK, 0, []),  # Wrong site ID
        (AGG_1_VALID_CERT, 1, "foobar", 0, 99, None, HTTPStatus.NOT_FOUND, None, None),  # bad list id
    ],
)
@pytest.mark.anyio
async def test_get_response_list_pagination_for_aggregator_cert(
    client: AsyncClient,
    response_list_uri_format: str,
    cert: str,
    site_id: int,
    response_set_id: str,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_http_response: HTTPStatus,
    expected_count: Optional[int],
    expected_statuses: Optional[list[ResponseType]],
):
    """Tests that fetching a response list paginates correctly (or fails predictably)"""
    response = await client.get(
        response_list_uri_format.format(site_id=site_id, response_list_id=response_set_id)
        + build_paging_params(start=start, limit=limit, changed_after=after),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_response)
    if expected_statuses is not None:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = ResponseListResponse.from_xml(body)
        assert parsed_response.all_ == expected_count
        assert parsed_response.results == len(expected_statuses)
        if parsed_response.Response_:
            assert len(parsed_response.Response_) == len(expected_statuses)
            assert [r.status for r in parsed_response.Response_] == expected_statuses
        else:
            assert len(expected_statuses) == 0, "A 0 length array is equivalent to a None Response_ list"
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, response_set_id, start, limit, after, expected_http_response, expected_count, expected_statuses",
    [
        (DEVICE_5_CERT, 5, DOE_HREF, 0, 99, None, HTTPStatus.OK, 1, [7]),
        (DEVICE_5_CERT, 5, RATE_HREF, 0, 99, None, HTTPStatus.OK, 1, [8]),
        (DEVICE_6_CERT, 6, RATE_HREF, 0, 99, None, HTTPStatus.OK, 0, []),
        (DEVICE_5_CERT, 6, RATE_HREF, 0, 99, None, HTTPStatus.FORBIDDEN, None, None),  # Wrong site id
    ],
)
@pytest.mark.anyio
async def test_get_response_list_pagination_for_device_cert(
    pg_base_config,
    client: AsyncClient,
    response_list_uri_format: str,
    cert: str,
    site_id: int,
    response_set_id: str,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_http_response: HTTPStatus,
    expected_count: Optional[int],
    expected_statuses: Optional[list[ResponseType]],
):
    """Tests that fetching a response list paginates correctly (or fails predictably)"""

    async with generate_async_session(pg_base_config) as session:
        # Add a DOE for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(DynamicOperatingEnvelope).values(
                dynamic_operating_envelope_id=101,
                site_control_group_id=1,
                site_id=5,
                calculation_log_id=None,
                changed_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                start_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                end_time=datetime(2025, 1, 2, 0, 5, 0, tzinfo=timezone.utc),
                duration_seconds=300,
                import_limit_active_watts=100,
                export_limit_watts=200,
            )
        )

        # Add a rate for site 5 (device cert) that can be cross referenced
        await session.execute(
            insert(TariffGeneratedRate).values(
                tariff_generated_rate_id=102,
                tariff_id=1,
                site_id=5,
                calculation_log_id=None,
                changed_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                start_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                duration_seconds=300,
                import_active_price=101,
                export_active_price=202,
                import_reactive_price=303,
                export_reactive_price=404,
            )
        )

        # Add a doe response for site 5 (device cert)
        await session.execute(
            insert(DynamicOperatingEnvelopeResponse).values(
                dynamic_operating_envelope_response_id=1001,
                dynamic_operating_envelope_id=101,
                site_id=5,
                response_type=7,
            )
        )

        # Add a rate response for site 5 (device cert)
        await session.execute(
            insert(TariffGeneratedRateResponse).values(
                tariff_generated_rate_response_id=1002,
                tariff_generated_rate_id=102,
                site_id=5,
                pricing_reading_type=PricingReadingType.IMPORT_ACTIVE_POWER_KWH,
                response_type=8,
            )
        )

        await session.commit()

    response = await client.get(
        response_list_uri_format.format(site_id=site_id, response_list_id=response_set_id)
        + build_paging_params(start=start, limit=limit, changed_after=after),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    assert_response_header(response, expected_http_response)
    if expected_statuses is not None:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = ResponseListResponse.from_xml(body)
        assert parsed_response.all_ == expected_count
        assert parsed_response.results == len(expected_statuses)
        if parsed_response.Response_:
            assert len(parsed_response.Response_) == len(expected_statuses)
            assert [r.status for r in parsed_response.Response_] == expected_statuses
        else:
            assert len(expected_statuses) == 0, "A 0 length array is equivalent to a None Response_ list"
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "cert, site_id, response_set_id, subject, request_type, expected_response_type, expected_http_status",
    [
        (
            AGG_1_VALID_CERT,
            1,
            RATE_HREF,
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 1, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            Response,
            PriceResponse,
            HTTPStatus.CREATED,
        ),
        (
            AGG_1_VALID_CERT,
            1,
            RATE_HREF,
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 1, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            PriceResponse,
            PriceResponse,
            HTTPStatus.CREATED,
        ),
        (
            AGG_1_VALID_CERT,
            0,
            RATE_HREF,
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 1, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            PriceResponse,
            None,
            HTTPStatus.FORBIDDEN,
        ),  # Can't send responses to aggregator end device
        (
            AGG_1_VALID_CERT,
            1,
            DOE_HREF,
            MridMapper.encode_doe_mrid(TEST_SCOPE, 1),
            DERControlResponse,
            DERControlResponse,
            HTTPStatus.CREATED,
        ),
        (
            AGG_1_VALID_CERT,
            1,
            DOE_HREF,
            MridMapper.encode_doe_mrid(TEST_SCOPE, 1),
            Response,
            DERControlResponse,
            HTTPStatus.CREATED,
        ),
        (
            AGG_1_VALID_CERT,
            0,
            DOE_HREF,
            MridMapper.encode_doe_mrid(TEST_SCOPE, 1),
            DERControlResponse,
            None,
            HTTPStatus.FORBIDDEN,
        ),  # Can't send responses to aggregator end device
        (
            AGG_2_VALID_CERT,
            1,
            RATE_HREF,
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 1, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            PriceResponse,
            None,
            HTTPStatus.BAD_REQUEST,
        ),  # Bad Aggregator
        (
            AGG_1_VALID_CERT,
            2,
            RATE_HREF,
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 1, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            PriceResponse,
            None,
            HTTPStatus.BAD_REQUEST,
        ),  # Bad Site ID
        (
            AGG_1_VALID_CERT,
            1,
            RATE_HREF,
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 99, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            PriceResponse,
            None,
            HTTPStatus.BAD_REQUEST,
        ),  # Bad tariff generated rate id
        (
            AGG_1_VALID_CERT,
            1,
            "foobar",
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 1, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            Response,
            None,
            HTTPStatus.NOT_FOUND,
        ),  # Invalid list id
        (
            AGG_1_VALID_CERT,
            1,
            DOE_HREF,
            MridMapper.encode_time_tariff_interval_mrid(TEST_SCOPE, 1, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),
            Response,
            None,
            HTTPStatus.BAD_REQUEST,
        ),  # The wrong list id
    ],
)
@pytest.mark.anyio
async def test_create_response_for_aggregator(
    pg_base_config,
    client: AsyncClient,
    response_list_uri_format: str,
    cert: str,
    site_id: int,
    response_set_id: str,
    subject: str,
    request_type: type[Response],
    expected_response_type: Optional[type[Response]],
    expected_http_status: HTTPStatus,
):
    """Tests the various ways aggregators can send responses to the various list endpoints"""
    async with generate_async_session(pg_base_config) as session:
        # Add a DOE for site 5 (device cert) that can be cross referenced
        rate_count_before = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRateResponse))
        ).scalar_one()
        doe_count_before = (
            await session.execute(select(func.count()).select_from(DynamicOperatingEnvelopeResponse))
        ).scalar_one()

    request_body = generate_class_instance(request_type, subject=subject, status=ResponseType.REJECTED_INVALID_EVENT)

    response = await client.post(
        response_list_uri_format.format(site_id=site_id, response_list_id=response_set_id),
        content=request_body.to_xml(),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    # Created responses don't have a content response
    if expected_http_status == HTTPStatus.CREATED:
        assert_response_header(response, expected_http_status, expected_content_type=None)
    else:
        assert_response_header(response, expected_http_status)

    async with generate_async_session(pg_base_config) as session:
        # Add a DOE for site 5 (device cert) that can be cross referenced
        rate_count_after = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRateResponse))
        ).scalar_one()
        doe_count_after = (
            await session.execute(select(func.count()).select_from(DynamicOperatingEnvelopeResponse))
        ).scalar_one()

    if expected_response_type:
        # We should receive a HREF to the created Response. Resolve it to ensure it's valid
        assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
        created_href = read_location_header(response)

        response = await client.get(created_href, headers={cert_header: urllib.parse.quote(cert)})
        assert_response_header(response, HTTPStatus.OK)

        parsed_response = expected_response_type.from_xml(read_response_body_string(response))
        assert parsed_response.status == request_body.status
        assert parsed_response.subject == subject
        assert_nowish(parsed_response.createdDateTime)

        assert (doe_count_before + rate_count_before + 1) == (doe_count_after + rate_count_after), "One new response"
    else:
        assert_error_response(response)
        assert (doe_count_before + rate_count_before) == (doe_count_after + rate_count_after), "No new responses"
