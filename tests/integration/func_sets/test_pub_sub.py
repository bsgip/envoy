import urllib.parse
from http import HTTPStatus

import envoy_schema.server.schema.uri as uris
import pytest
from envoy_schema.server.schema.sep2.end_device import EndDeviceRequest
from envoy_schema.server.schema.sep2.metering_mirror import MirrorMeterReading
from envoy_schema.server.schema.sep2.types import DeviceCategory
from envoy_schema.server.schema.uri import EndDeviceListUri
from httpx import AsyncClient

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.fake.generator import generate_class_instance
from tests.integration.integration_server import cert_header
from tests.integration.response import assert_response_header, read_location_header, read_response_body_string
from tests.unit.mocks import MockedAsyncClient


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
