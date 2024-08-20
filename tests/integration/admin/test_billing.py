import json
from datetime import datetime, timezone
from decimal import Decimal
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_datetime_equal
from envoy_schema.admin.schema.billing import (
    AggregatorBillingResponse,
    CalculationLogBillingResponse,
    SiteBillingRequest,
    SiteBillingResponse,
)
from envoy_schema.admin.schema.uri import AggregatorBillingUri, CalculationLogBillingUri, SitePeriodBillingUri
from httpx import AsyncClient

from tests.integration.response import assert_response_header, read_response_body_string


@pytest.mark.parametrize(
    "period_start_str, period_end_str",
    [
        ("2023-09-10 00:00+10:00", "2023-09-11 00:00+10:00"),  # AEST timezone (short form)
        ("2023-09-10T00:00:00.0000+10:00", "2023-09-11T00:00:00.0000+10:00"),  # AEST timezone (long form)
        ("2023-09-09T14:00Z", "2023-09-10T14:00Z"),  # UTC timezone
    ],
)
@pytest.mark.anyio
async def test_fetch_aggregator_billing_data_timezone(
    pg_billing_data, admin_client_auth: AsyncClient, period_start_str: str, period_end_str: str
):
    uri = AggregatorBillingUri.format(
        aggregator_id=1, tariff_id=1, period_start=period_start_str, period_end=period_end_str
    )
    response = await admin_client_auth.get(uri)
    assert_response_header(response, expected_status_code=HTTPStatus.OK, expected_content_type="application/json")
    json_body = json.loads(read_response_body_string(response))
    body = AggregatorBillingResponse.model_validate(json_body)

    assert_datetime_equal(body.period_start, datetime(2023, 9, 10, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")))
    assert_datetime_equal(body.period_end, datetime(2023, 9, 11, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")))
    assert body.aggregator_id == 1
    assert body.tariff_id == 1

    assert [
        (t.site_id, t.import_active_price, t.export_active_price, t.import_reactive_price, t.export_reactive_price)
        for t in body.active_tariffs
    ] == [
        (1, Decimal("1.1"), Decimal("-1.2"), Decimal("1.3"), Decimal("-1.4")),
        (1, Decimal("2.1"), Decimal("-2.2"), Decimal("2.3"), Decimal("-2.4")),
        (1, Decimal("3.1"), Decimal("-3.2"), Decimal("3.3"), Decimal("-3.4")),
        (2, Decimal("6.1"), Decimal("-6.2"), Decimal("6.3"), Decimal("-6.4")),
    ]

    assert [(d.site_id, d.import_limit_active_watts, d.export_limit_watts) for d in body.active_does] == [
        (1, Decimal("1.11"), Decimal("-1.22")),
        (1, Decimal("2.11"), Decimal("-2.22")),
        (2, Decimal("5.11"), Decimal("-5.22")),
    ]

    assert [(r.site_id, r.value) for r in body.wh_readings] == [
        (1, Decimal("110")),
        (1, Decimal("220")),
        (2, Decimal("770")),
    ]

    assert [(r.site_id, r.value) for r in body.varh_readings] == [
        (1, Decimal("550")),
    ]

    assert [(r.site_id, r.value) for r in body.watt_readings] == [
        (1, Decimal("990")),
        (1, Decimal("10100")),
    ]


@pytest.mark.anyio
async def test_fetch_aggregator_billing_data_bad_id(pg_billing_data, admin_client_auth: AsyncClient):
    uri = AggregatorBillingUri.format(
        aggregator_id=99, tariff_id=1, period_start="2023-09-10 00:00+10:00", period_end="2023-09-11 00:00+10:00"
    )
    response = await admin_client_auth.get(uri)
    assert_response_header(
        response, expected_status_code=HTTPStatus.NOT_FOUND, expected_content_type="application/json"
    )


@pytest.mark.anyio
async def test_fetch_calculation_log_billing_data_timezone(pg_billing_data, admin_client_auth: AsyncClient):
    uri = CalculationLogBillingUri.format(calculation_log_id=4, tariff_id=1)
    response = await admin_client_auth.get(uri)
    assert_response_header(response, expected_status_code=HTTPStatus.OK, expected_content_type="application/json")
    json_body = json.loads(read_response_body_string(response))
    body = CalculationLogBillingResponse.model_validate(json_body)

    assert body.calculation_log_id == 4
    assert body.tariff_id == 1

    assert [
        (t.site_id, t.import_active_price, t.export_active_price, t.import_reactive_price, t.export_reactive_price)
        for t in body.active_tariffs
    ] == [
        (1, Decimal("1.1"), Decimal("-1.2"), Decimal("1.3"), Decimal("-1.4")),
        (1, Decimal("2.1"), Decimal("-2.2"), Decimal("2.3"), Decimal("-2.4")),
        (1, Decimal("3.1"), Decimal("-3.2"), Decimal("3.3"), Decimal("-3.4")),
        (3, Decimal("7.1"), Decimal("-7.2"), Decimal("7.3"), Decimal("-7.4")),
    ]

    assert [(d.site_id, d.import_limit_active_watts, d.export_limit_watts) for d in body.active_does] == [
        (1, Decimal("1.11"), Decimal("-1.22")),
        (1, Decimal("2.11"), Decimal("-2.22")),
        (3, Decimal("6.11"), Decimal("-6.22")),
    ]

    assert [(r.site_id, r.value) for r in body.wh_readings] == [
        (1, Decimal("110")),
        (1, Decimal("220")),
        (3, Decimal("880")),
    ]

    assert [(r.site_id, r.value) for r in body.varh_readings] == [
        (1, Decimal("550")),
    ]

    assert [(r.site_id, r.value) for r in body.watt_readings] == [
        (1, Decimal("990")),
        (1, Decimal("10100")),
    ]


@pytest.mark.anyio
async def test_fetch_calculation_log_billing_data_bad_id(pg_billing_data, admin_client_auth: AsyncClient):
    uri = CalculationLogBillingUri.format(calculation_log_id=99, tariff_id=1)
    response = await admin_client_auth.get(uri)
    assert_response_header(
        response, expected_status_code=HTTPStatus.NOT_FOUND, expected_content_type="application/json"
    )


@pytest.mark.anyio
async def test_fetch_sites_billing_data(pg_billing_data, admin_client_auth: AsyncClient):
    uri = SitePeriodBillingUri
    request = SiteBillingRequest(
        site_ids=[1, 2, 4],
        tariff_id=1,
        period_start=datetime(2023, 9, 9, 14, 0, tzinfo=timezone.utc),
        period_end=datetime(2023, 9, 10, 14, 0, tzinfo=timezone.utc),
    )
    response = await admin_client_auth.post(uri, content=request.model_dump_json())
    assert_response_header(response, expected_status_code=HTTPStatus.OK, expected_content_type="application/json")
    json_body = json.loads(read_response_body_string(response))
    body = SiteBillingResponse.model_validate(json_body)

    assert_datetime_equal(body.period_start, datetime(2023, 9, 10, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")))
    assert_datetime_equal(body.period_end, datetime(2023, 9, 11, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")))
    assert body.site_ids == [1, 2, 4]
    assert body.tariff_id == 1

    assert [
        (t.site_id, t.import_active_price, t.export_active_price, t.import_reactive_price, t.export_reactive_price)
        for t in body.active_tariffs
    ] == [
        (1, Decimal("1.1"), Decimal("-1.2"), Decimal("1.3"), Decimal("-1.4")),
        (1, Decimal("2.1"), Decimal("-2.2"), Decimal("2.3"), Decimal("-2.4")),
        (1, Decimal("3.1"), Decimal("-3.2"), Decimal("3.3"), Decimal("-3.4")),
        (2, Decimal("6.1"), Decimal("-6.2"), Decimal("6.3"), Decimal("-6.4")),
    ]

    assert [(d.site_id, d.import_limit_active_watts, d.export_limit_watts) for d in body.active_does] == [
        (1, Decimal("1.11"), Decimal("-1.22")),
        (1, Decimal("2.11"), Decimal("-2.22")),
        (2, Decimal("5.11"), Decimal("-5.22")),
    ]

    assert [(r.site_id, r.value) for r in body.wh_readings] == [
        (1, Decimal("110")),
        (1, Decimal("220")),
        (2, Decimal("770")),
    ]

    assert [(r.site_id, r.value) for r in body.varh_readings] == [
        (1, Decimal("550")),
    ]

    assert [(r.site_id, r.value) for r in body.watt_readings] == [
        (1, Decimal("990")),
        (1, Decimal("10100")),
    ]
