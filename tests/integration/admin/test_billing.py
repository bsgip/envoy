import json
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from envoy_schema.admin.schema.billing import BillingResponse
from envoy_schema.admin.schema.uri import BillingUri
from httpx import AsyncClient

from tests.assert_time import assert_datetime_equal
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
async def test_fetch_billing_data_timezone(
    pg_billing_data, admin_client_auth: AsyncClient, period_start_str: str, period_end_str: str
):
    uri = BillingUri.format(aggregator_id=1, tariff_id=1, period_start=period_start_str, period_end=period_end_str)
    response = await admin_client_auth.get(uri)
    assert_response_header(response, expected_status_code=HTTPStatus.OK, expected_content_type="application/json")
    json_body = json.loads(read_response_body_string(response))
    body = BillingResponse.model_validate(json_body)

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
        (1, Decimal("1.1")),
        (1, Decimal("2.2")),
        (2, Decimal("7.7")),
    ]

    assert [(r.site_id, r.value) for r in body.varh_readings] == [
        (1, Decimal("5.5")),
    ]

    assert [(r.site_id, r.value) for r in body.watt_readings] == [
        (1, Decimal("9.9")),
        (1, Decimal("101.0")),
    ]
