import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import envoy_schema.server.schema.uri as uris
import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.der import DERCapability
from envoy_schema.server.schema.sep2.end_device import EndDeviceRequest
from envoy_schema.server.schema.sep2.metering_mirror import MirrorMeterReading
from envoy_schema.server.schema.sep2.pub_sub import Notification as Sep2Notification
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionEncoding, SubscriptionListResponse
from envoy_schema.server.schema.sep2.types import DeviceCategory
from envoy_schema.server.schema.uri import EndDeviceListUri
from httpx import AsyncClient
from sqlalchemy import select

from envoy.server.crud.end_device import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.crud.subscription import select_subscription_by_id
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.model.subscription import Subscription
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_FINGERPRINT as AGG_3_VALID_CERT
from tests.data.certificates.certificate6 import TEST_CERTIFICATE_FINGERPRINT as DEVICE_5_CERT
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
def sub_list_uri_format():
    return "/edev/{site_id}/sub"


@pytest.fixture
def sub_uri_format():
    return "/edev/{site_id}/sub/{subscription_id}"


def subscribable_resource_hrefs(site_id: int, pricing_reading_type_id: int) -> list[str]:
    """Very coarse list of resource endpoints that can be subscribed (keyed for a particular site_id)"""
    return [
        f"/edev/{site_id}/derp/doe/derc",
        f"/edev/{site_id}",
        f"/edev/{site_id}/der/1/dercap",
        f"/edev/{site_id}/der/1/dera",
        f"/edev/{site_id}/der/1/ders",
        f"/edev/{site_id}/der/1/derg",
        f"/edev/{site_id}/tp/1/rc",
        f"/upt/{site_id}/mr/{pricing_reading_type_id}/rs/all/r",
    ]


@pytest.mark.parametrize(
    "cert, site_id, expected_sub_ids",
    [
        (AGG_1_VALID_CERT, 4, [4, 5]),
        (AGG_2_VALID_CERT, 3, [3]),
        (
            AGG_1_VALID_CERT,
            0,
            [1, 2, 4, 5],
        ),  # aggregator end device should get all subs across all sites (for this agg)
        (AGG_2_VALID_CERT, 0, [3]),  # aggregator end device should get all subs across all sites (for this agg)
        (AGG_3_VALID_CERT, 4, []),  # Inaccessible to this aggregator
        (AGG_3_VALID_CERT, 0, []),  # Agg3 has 0 subscriptions across all sites
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
    "cert, site_id, expected_status",
    [
        (AGG_1_VALID_CERT, 1, HTTPStatus.OK),  # Control - should work fine
        (DEVICE_5_CERT, 5, HTTPStatus.FORBIDDEN),  # device cert
        (DEVICE_5_CERT, 6, HTTPStatus.FORBIDDEN),  # device cert
        (DEVICE_5_CERT, 0, HTTPStatus.FORBIDDEN),  # device cert
        (UNREGISTERED_CERT, 5, HTTPStatus.FORBIDDEN),  # site DNE
        (UNREGISTERED_CERT, 0, HTTPStatus.FORBIDDEN),  # site DNE
    ],
)
@pytest.mark.anyio
async def test_get_subscription_list_by_aggregator_forbidden_cases(
    client: AsyncClient, cert: str, expected_status: HTTPStatus, site_id: int, sub_list_uri_format
):
    """Validates that fetching subscription lists only works for aggregator certs"""

    response = await client.get(
        sub_list_uri_format.format(site_id=site_id) + build_paging_params(limit=100),
        headers={cert_header: urllib.parse.quote(cert)},
    )
    assert_response_header(response, expected_status)
    if expected_status != HTTPStatus.OK:
        assert_error_response(response)


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
        sub_uri_format.format(site_id=site_id, subscription_id=sub_id),
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
async def test_delete_subscription(
    client: AsyncClient, pg_base_config, sub_id: int, cert: str, site_id: int, expected_404: bool, sub_uri_format
):
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(Subscription))
        initial_count = len(resp.scalars().all())

    response = await client.delete(
        sub_uri_format.format(site_id=site_id, subscription_id=sub_id),
        headers={cert_header: urllib.parse.quote(cert)},
    )

    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(Subscription))
        after_count = len(resp.scalars().all())

    if expected_404:
        assert_response_header(response, HTTPStatus.NOT_FOUND, expected_content_type=None)
        assert initial_count == after_count
    else:
        assert_response_header(response, HTTPStatus.NO_CONTENT, expected_content_type=None)
        assert (initial_count - 1) == after_count


@pytest.mark.parametrize("use_aggregator_edev", [True, False])
@pytest.mark.anyio
async def test_create_doe_subscription(
    pg_base_config, client: AsyncClient, sub_list_uri_format: str, use_aggregator_edev: bool
):
    """When creating a sub check to see if it persists and is correctly assigned to the aggregator"""

    edev_id: int = 0 if use_aggregator_edev else 1

    insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
    insert_request.encoding = SubscriptionEncoding.XML
    insert_request.notificationURI = "https://example.com/456?foo=bar"
    insert_request.subscribedResource = f"/edev/{edev_id}/derp/doe/derc"
    response = await client.post(
        sub_list_uri_format.format(site_id=edev_id),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=Sep2Subscription.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    assert len(read_response_body_string(response)) == 0
    inserted_href = read_location_header(response)

    # now lets grab the sub we just created
    response = await client.get(inserted_href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    response_body = read_response_body_string(response)
    assert len(response_body) > 0
    parsed_response: Sep2Subscription = Sep2Subscription.from_xml(response_body)
    assert parsed_response.href in inserted_href
    assert parsed_response.notificationURI == insert_request.notificationURI
    assert parsed_response.subscribedResource == insert_request.subscribedResource
    assert parsed_response.limit == insert_request.limit

    # check that other aggregators can't fetch it
    response = await client.get(inserted_href, headers={cert_header: urllib.parse.quote(AGG_2_VALID_CERT)})
    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)

    # Validate the DB record is properly scoped
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(Subscription).order_by(Subscription.subscription_id.desc()).limit(1))
        created_sub = resp.scalars().first()
        if use_aggregator_edev:
            assert created_sub.scoped_site_id is None, "Aggregator scoped requests are site unscoped"
        else:
            assert created_sub.scoped_site_id == edev_id, "Regular requests are site scoped"


@pytest.mark.parametrize(
    "invalid_resource",
    subscribable_resource_hrefs(site_id=3, pricing_reading_type_id=2),  # Site 3 belongs to agg 2
)
@pytest.mark.anyio
async def test_create_subscription_site_id_outside_aggregator(
    client: AsyncClient, sub_list_uri_format: str, invalid_resource: str
):
    """When creating a sub check that the edev belongs to the requesting aggregator"""

    # Test for both the aggregator end device AND the regular end device
    for edev_id in [VIRTUAL_END_DEVICE_SITE_ID, 1]:
        insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
        insert_request.encoding = SubscriptionEncoding.XML
        insert_request.notificationURI = "https://example.com/456?foo=bar"
        insert_request.subscribedResource = invalid_resource
        response = await client.post(
            sub_list_uri_format.format(site_id=edev_id),
            headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
            content=Sep2Subscription.to_xml(insert_request),
        )
        assert_response_header(response, HTTPStatus.BAD_REQUEST)
        assert_error_response(response)


@pytest.mark.parametrize("sub_href", subscribable_resource_hrefs(site_id=1, pricing_reading_type_id=1))
@pytest.mark.anyio
async def test_create_site_scoped_subscription_entry_added_to_db(
    pg_base_config, client: AsyncClient, sub_list_uri_format: str, sub_href: str
):
    """Simple test that subscription creation works across endpoints from subscribable_resource_hrefs
    (when the subscription is going to be scoped to a single site)"""
    edev_id = 1

    insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
    insert_request.encoding = SubscriptionEncoding.XML
    insert_request.notificationURI = "https://example.com/456?foo=bar"
    insert_request.subscribedResource = sub_href
    response = await client.post(
        sub_list_uri_format.format(site_id=edev_id),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=Sep2Subscription.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    location_header = read_location_header(response)
    assert location_header
    sub_id = int(location_header.split("/")[-1])  # the last part of the href should be a subscription id

    # Validate the DB record is properly scoped
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(Subscription).where(Subscription.subscription_id == sub_id).limit(1))
        created_sub = resp.scalars().first()
        assert created_sub.scoped_site_id == edev_id, "Expected a site scoped sub"
        assert_nowish(created_sub.changed_time)


@pytest.mark.parametrize(
    "sub_href", subscribable_resource_hrefs(site_id=VIRTUAL_END_DEVICE_SITE_ID, pricing_reading_type_id=1)
)
@pytest.mark.anyio
async def test_create_unscoped_subscription_entry_added_to_db(
    pg_base_config, client: AsyncClient, sub_list_uri_format: str, sub_href: str
):
    """Simple test that subscription creation works across endpoints from subscribable_resource_hrefs
    (when the subscription is going to be done via the aggregator end device)"""
    edev_id = VIRTUAL_END_DEVICE_SITE_ID

    insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
    insert_request.encoding = SubscriptionEncoding.XML
    insert_request.notificationURI = "https://example.com/456?foo=bar"
    insert_request.subscribedResource = sub_href
    response = await client.post(
        sub_list_uri_format.format(site_id=edev_id),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=Sep2Subscription.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    location_header = read_location_header(response)
    assert location_header
    sub_id = int(location_header.split("/")[-1])  # the last part of the href should be a subscription id

    # Validate the DB record is properly scoped
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(Subscription).where(Subscription.subscription_id == sub_id).limit(1))
        created_sub = resp.scalars().first()
        assert created_sub.scoped_site_id is None, "Expected a unscoped sub"
        assert_nowish(created_sub.changed_time)


@pytest.mark.anyio
async def test_create_subscription_site_id_mismatches_subscription(client: AsyncClient, sub_list_uri_format: str):
    """When creating a sub check that the subscribed resource owns the requesting edev"""

    # Requests to /edev/0/* must have subbed resource be underneath /edev/0/*
    for subbed_resource in subscribable_resource_hrefs(site_id=1, pricing_reading_type_id=1):
        insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
        insert_request.encoding = SubscriptionEncoding.XML
        insert_request.notificationURI = "https://example.com/456?foo=bar"
        insert_request.subscribedResource = subbed_resource
        response = await client.post(
            sub_list_uri_format.format(site_id=0),
            headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
            content=Sep2Subscription.to_xml(insert_request),
        )
        assert_response_header(response, HTTPStatus.BAD_REQUEST)
        assert_error_response(response)

    # Requests to /edev/1/* must have subbed resource be underneath /edev/1/*
    for subbed_resource in subscribable_resource_hrefs(site_id=0, pricing_reading_type_id=1):
        insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
        insert_request.encoding = SubscriptionEncoding.XML
        insert_request.notificationURI = "https://example.com/456?foo=bar"
        insert_request.subscribedResource = subbed_resource
        response = await client.post(
            sub_list_uri_format.format(site_id=1),
            headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
            content=Sep2Subscription.to_xml(insert_request),
        )
        assert_response_header(response, HTTPStatus.BAD_REQUEST)
        assert_error_response(response)


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
    assert await notifications_enabled.wait_for_request(timeout_seconds=30)

    expected_notification_uri = "https://example.com:11/path/"  # from the base_config.sql
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, expected_notification_uri)] == 1

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
        content=MirrorMeterReading.to_xml(mmr, skip_empty=False, exclude_none=True, exclude_unset=True),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)

    # Wait for the notification to propagate
    assert await notifications_enabled.wait_for_request(timeout_seconds=30)

    expected_notification_uri = "https://example.com:55/path/"  # from the base_config.sql
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, expected_notification_uri)] == 1

    # Simple check on the notification content
    assert "dead" not in notifications_enabled.logged_requests[0].content
    assert "beef" in notifications_enabled.logged_requests[0].content


@pytest.mark.anyio
async def test_der_capability_subscription(
    client: AsyncClient, sub_list_uri_format: str, notifications_enabled: MockedAsyncClient
):
    """Create a sub and see if an updated DER capability generates a notification"""

    # subscribe
    insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
    insert_request.encoding = SubscriptionEncoding.XML
    insert_request.notificationURI = "https://example.com/456?foo=bar"
    insert_request.subscribedResource = uris.DERCapabilityUri.format(site_id=1, der_id=PUBLIC_SITE_DER_ID)
    response = await client.post(
        sub_list_uri_format.format(site_id=1),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=Sep2Subscription.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)

    # create an updated capability
    updated_cap: DERCapability = generate_class_instance(DERCapability, generate_relationships=True)
    updated_cap.modesSupported = "3"
    updated_cap.doeModesSupported = "2"
    response = await client.put(
        uris.DERCapabilityUri.format(site_id=1, der_id=PUBLIC_SITE_DER_ID),
        content=updated_cap.to_xml(skip_empty=False, exclude_none=True, exclude_unset=True),
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )
    assert_response_header(response, HTTPStatus.NO_CONTENT, expected_content_type=None)

    # check for notification
    assert await notifications_enabled.wait_for_request(timeout_seconds=30)
    expected_notification_uri = insert_request.notificationURI
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, expected_notification_uri)] == 1

    notification = Sep2Notification.from_xml(notifications_enabled.logged_requests[0].content)
    assert notification.subscribedResource == insert_request.subscribedResource
    assert notification.resource is not None

    assert_class_instance_equality(
        DERCapability,
        updated_cap,
        notification.resource,
        ignored_properties=set(["href", "type", "subscribable"]),
    )


@pytest.mark.parametrize("use_aggregator_edev", [True, False])
@pytest.mark.anyio
async def test_subscription_create_unavailable_for_device_cert(
    pg_base_config, client: AsyncClient, sub_list_uri_format: str, use_aggregator_edev: bool
):
    """When creating a sub check check to make sure it isn't for a device cert"""

    edev_id: int = 0 if use_aggregator_edev else 5

    insert_request: Sep2Subscription = generate_class_instance(Sep2Subscription)
    insert_request.encoding = SubscriptionEncoding.XML
    insert_request.notificationURI = "https://example.com/456?foo=bar"
    insert_request.subscribedResource = f"/edev/{edev_id}/derp/doe/derc"
    response = await client.post(
        sub_list_uri_format.format(site_id=edev_id),
        headers={cert_header: urllib.parse.quote(DEVICE_5_CERT)},
        content=Sep2Subscription.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN)
    assert_error_response(response)
