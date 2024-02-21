import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import envoy_schema.server.schema.uri as uris
import pytest
from envoy_schema.server.schema.sep2.end_device import EndDeviceRequest
from envoy_schema.server.schema.sep2.metering_mirror import MirrorMeterReading
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionListResponse
from envoy_schema.server.schema.sep2.types import DeviceCategory
from envoy_schema.server.schema.uri import EndDeviceListUri
from httpx import AsyncClient

from envoy.server.crud.subscription import select_subscription_by_id
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_FINGERPRINT as AGG_3_VALID_CERT
from tests.data.fake.generator import generate_class_instance
from tests.integration.integration_server import cert_header
from tests.integration.request import build_paging_params
from tests.integration.response import (
    assert_error_response,
    assert_response_header,
    read_location_header,
    read_response_body_string,
)
from tests.postgres_testing import generate_async_session
from tests.unit.mocks import MockedAsyncClient


@pytest.fixture
def sub_list_uri_format():
    return "/edev/{site_id}/sub"


@pytest.fixture
def sub_uri_format():
    return "/edev/{site_id}/sub/{subscription_id}"


@pytest.mark.parametrize(
    "cert, site_id, expected_sub_ids",
    [
        (AGG_1_VALID_CERT, 4, [4, 5]),
        (AGG_2_VALID_CERT, 3, [3]),
        (AGG_3_VALID_CERT, 4, []),  # Inaccessible to this aggregator
        (AGG_1_VALID_CERT, 1, []),  # Nothing under site
        (AGG_1_VALID_CERT, 99, []),  # site DNE
    ],
)
@pytest.mark.anyio
async def test_get_subscription_list_by_aggregator(
    pg_base_config, client: AsyncClient, expected_sub_ids: list[int], cert: str, site_id: int, sub_list_uri_format
):
    """Simple test of a valid get for different aggregator certs - validates that the response looks like XML
    and that it contains the expected subscriptions associated with each aggregator/site"""

    # Start by updating our subscription 5 to appear under site 4 (to ensure we get multiple in a list)
    async with generate_async_session(pg_base_config) as session:
        sub_5 = await select_subscription_by_id(session, 1, 5)
        sub_5.scoped_site_id = 4
        await session.commit()

    response = await client.get(
        sub_list_uri_format.format(site_id=site_id) + build_paging_params(limit=100),
        headers={cert_header: urllib.parse.quote(cert)},
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: SubscriptionListResponse = SubscriptionListResponse.from_xml(body)
    assert parsed_response.all_ == len(expected_sub_ids), f"received body:\n{body}"
    assert parsed_response.results == len(expected_sub_ids), f"received body:\n{body}"

    if len(expected_sub_ids) > 0:
        assert parsed_response.subscriptions, f"received body:\n{body}"
        assert len(parsed_response.subscriptions) == len(expected_sub_ids), f"received body:\n{body}"

        # Pull sub id from the href - hacky but will work for this test
        assert [int(ed.href[-1]) for ed in parsed_response.subscriptions] == expected_sub_ids


@pytest.mark.parametrize(
    "start, limit, after, expected_sub_ids",
    [
        (0, 99, None, [4, 5]),
        (0, 99, datetime(2024, 1, 2, 14, 22, 33, tzinfo=timezone.utc), [4, 5]),
        (0, None, datetime(2024, 1, 2, 14, 22, 34, tzinfo=timezone.utc), [5]),
        (0, None, datetime(2024, 1, 2, 15, 22, 34, tzinfo=timezone.utc), []),
        (1, 1, datetime(2024, 1, 2, 14, 22, 34, tzinfo=timezone.utc), []),
        (0, 1, None, [4]),
        (1, 1, None, [5]),
        (2, 1, None, []),
    ],
)
@pytest.mark.anyio
async def test_get_subscription_list_by_page(
    pg_base_config,
    client: AsyncClient,
    expected_sub_ids: list[int],
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    sub_list_uri_format,
):
    """Tests the pagination on the sub list endpoint"""

    cert = AGG_1_VALID_CERT
    site_id = 4

    # Start by updating our subscription 5 to appear under site 4 (to ensure we get multiple in a list)
    async with generate_async_session(pg_base_config) as session:
        sub_5 = await select_subscription_by_id(session, 1, 5)
        sub_5.scoped_site_id = 4
        await session.commit()

    response = await client.get(
        sub_list_uri_format.format(site_id=site_id)
        + build_paging_params(limit=limit, start=start, changed_after=after),
        headers={cert_header: urllib.parse.quote(cert)},
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: SubscriptionListResponse = SubscriptionListResponse.from_xml(body)
    assert parsed_response.results == len(expected_sub_ids), f"received body:\n{body}"

    if len(expected_sub_ids) > 0:
        assert parsed_response.subscriptions, f"received body:\n{body}"
        assert len(parsed_response.subscriptions) == len(expected_sub_ids), f"received body:\n{body}"

        # Pull sub id from the href - hacky but will work for this test
        assert [int(ed.href[-1]) for ed in parsed_response.subscriptions] == expected_sub_ids


@pytest.mark.parametrize(
    "cert, site_id, sub_id, expected_404",
    [
        (AGG_1_VALID_CERT, 4, 4, False),
        (AGG_2_VALID_CERT, 3, 3, False),
        (AGG_3_VALID_CERT, 3, 3, True),  # Inaccessible to this aggregator
        (AGG_1_VALID_CERT, 99, 1, True),  # invalid site id
        (AGG_1_VALID_CERT, 1, 1, True),  # wrong site id
    ],
)
@pytest.mark.anyio
async def test_get_subscription_by_aggregator(
    client: AsyncClient, sub_id: int, cert: str, site_id: int, expected_404: bool, sub_uri_format
):
    """Simple test of a valid get for different aggregator certs - validates that the response looks like XML
    and that it contains the expected subscription associated with each aggregator/site"""

    response = await client.get(
        sub_uri_format.format(site_id=site_id, subscription_id=sub_id) + build_paging_params(limit=100),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    if expected_404:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: Sep2Subscription = Sep2Subscription.from_xml(body)
        assert int(parsed_response.href[-1]) == sub_id


@pytest.mark.anyio
async def test_create_end_device_subscription(client: AsyncClient, notifications_enabled: MockedAsyncClient):
    """When creating an end_device check to see if it generates a notification"""

    # The base configuration already has Subscription 1 that will pickup this new EndDevice
    insert_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    insert_request.postRate = 123
    insert_request.deviceCategory = "{0:x}".format(int(DeviceCategory.HOT_TUB))
    response = await client.post(
        EndDeviceListUri,
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=EndDeviceRequest.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    assert len(read_response_body_string(response)) == 0
    inserted_href = read_location_header(response)

    # Wait for the notification to propagate
    assert await notifications_enabled.wait_for_request(timeout_seconds=10)

    expected_notification_uri = "https://example.com:11/path/"  # from the base_config.sql
    assert notifications_enabled.get_calls == 0
    assert notifications_enabled.post_calls == 1
    assert notifications_enabled.post_calls_by_uri[expected_notification_uri] == 1

    # Simple check on the notification content
    assert inserted_href in notifications_enabled.logged_requests[0].content
    assert insert_request.lFDI in notifications_enabled.logged_requests[0].content
    assert str(insert_request.sFDI) in notifications_enabled.logged_requests[0].content


@pytest.mark.anyio
async def test_submit_conditional_reading(client: AsyncClient, notifications_enabled: MockedAsyncClient):
    """Submits a batch of readings to a mup and checks to see if they generate notifications"""

    # We submit two readings - only one will pass the subscription conditions on Subscription 5
    mmr: MirrorMeterReading = MirrorMeterReading.model_validate(
        {
            "mRID": "1234",
            "mirrorReadingSets": [
                {
                    "mRID": "1234abc",
                    "timePeriod": {
                        "duration": 603,
                        "start": 1341579365,
                    },
                    "readings": [
                        # This is within the conditional bounds and won't generate a notification
                        {"value": 9, "timePeriod": {"duration": 301, "start": 1341579365}, "localID": "dead"},
                        # This is outside the conditional bounds and WILL generate a notification
                        {"value": -10, "timePeriod": {"duration": 302, "start": 1341579666}, "localID": "beef"},
                    ],
                }
            ],
        }
    )
    mup_id = 1

    # submit the readings and then Subscription 5 will pickup these notifications
    response = await client.post(
        uris.MirrorUsagePointUri.format(mup_id=mup_id),
        content=MirrorMeterReading.to_xml(mmr, skip_empty=True),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)

    # Wait for the notification to propagate
    assert await notifications_enabled.wait_for_request(timeout_seconds=10)

    expected_notification_uri = "https://example.com:55/path/"  # from the base_config.sql
    assert notifications_enabled.get_calls == 0
    assert notifications_enabled.post_calls == 1
    assert notifications_enabled.post_calls_by_uri[expected_notification_uri] == 1

    # Simple check on the notification content
    assert "dead" not in notifications_enabled.logged_requests[0].content
    assert "beef" in notifications_enabled.logged_requests[0].content