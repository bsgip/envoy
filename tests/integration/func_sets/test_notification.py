import urllib.parse
from datetime import datetime
from http import HTTPStatus

import pytest
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.uri import EndDeviceUri, MirrorUsagePointUri
from httpx import AsyncClient
from sqlalchemy import delete, insert

from envoy.notification.task.transmit import HEADER_NOTIFICATION_ID
from envoy.server.model.subscription import Subscription, SubscriptionResource
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.integration.integration_server import cert_header


@pytest.mark.anyio
async def test_delete_site_generates_notification(
    client: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests deleting sites with an active subscription generates notifications via the MockedAsyncClient"""
    # Create a subscription to actually pickup these changes
    subscription1_uri = "http://my.example:542/uri"
    subscription2_uri = "https://my.other.example:542/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # this is unscoped
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.SITE,
                resource_id=None,
                scoped_site_id=None,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        # This is scoped to site2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.SITE,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    resp = await client.delete(
        EndDeviceUri.format(site_id=1), headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

    # Sub 1 will pickup the deletion (as it's unscoped), sub 2 gets nothing (scoped to site 2)
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1

    assert all([HEADER_NOTIFICATION_ID in r.headers for r in notifications_enabled.logged_requests])
    assert len(set([r.headers[HEADER_NOTIFICATION_ID] for r in notifications_enabled.logged_requests])) == len(
        notifications_enabled.logged_requests
    ), "Expected unique notification ids for each request"

    # Do a really simple content check on the outgoing XML to ensure the notifications contain the expected
    # entities for each subscription
    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri
                and "site1-lfdi".upper() in r.content  # unique to site 1
                and "<status>4</status>" in r.content  # This is a deletion notification
            ]
        )
        == 1
    ), "The NMI for site 1 should've been in the notification batch"


@pytest.mark.anyio
async def test_delete_mup_generates_notification(
    client: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests deleting a mup with an active subscription generates notifications via the MockedAsyncClient for each
    child reading (the MUP itself doesn't generate a notification)"""
    # Create a subscription to actually pickup these changes
    subscription1_uri = "http://my.example:542/uri"
    subscription2_uri = "https://my.other.example:542/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # this is unscoped
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.READING,
                resource_id=None,
                scoped_site_id=None,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        # This is scoped to site2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.READING,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    resp = await client.delete(
        MirrorUsagePointUri.format(mup_id=1), headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

    # Sub 1 will pickup the deletion (as it's unscoped), sub 2 gets nothing (scoped to site 2)
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1

    assert all([HEADER_NOTIFICATION_ID in r.headers for r in notifications_enabled.logged_requests])
    assert len(set([r.headers[HEADER_NOTIFICATION_ID] for r in notifications_enabled.logged_requests])) == len(
        notifications_enabled.logged_requests
    ), "Expected unique notification ids for each request"

    # Do a really simple content check on the outgoing XML to ensure the notifications contain the expected
    # entities for each subscription
    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri
                and "2b67" in r.content  # LocalID Value 11111 (unique to reading 1)
                and "56ce" in r.content  # LocalID Value 22222 (unique to reading 2)
                and "<status>4</status>" in r.content  # This is a deletion notification
            ]
        )
        == 1
    ), "The readings (1 and 2) for mup 1 should've been in the notification batch"
