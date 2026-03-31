import asyncio
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Union
from zoneinfo import ZoneInfo

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.config import RuntimeServerConfigRequest
from envoy_schema.admin.schema.pricing import TariffComponentRequest, TariffGeneratedRateRequest, TariffRequest
from envoy_schema.admin.schema.site import SiteUpdateRequest
from envoy_schema.admin.schema.site_control import (
    SiteControlGroupDefaultRequest,
    SiteControlGroupRequest,
    SiteControlRequest,
    UpdateDefaultValue,
)
from envoy_schema.admin.schema.uri import (
    ServerConfigRuntimeUri,
    SiteControlGroupDefaultUri,
    SiteControlGroupListUri,
    SiteControlUri,
    SiteUri,
    TariffComponentCreateUri,
    TariffCreateUri,
    TariffGeneratedRateCreateUri,
)
from envoy_schema.server.schema.sep2.types import RoleFlagsType
from httpx import AsyncClient
from sqlalchemy import delete, insert, select

from envoy.notification.task.transmit import HEADER_NOTIFICATION_ID
from envoy.server.api.response import SEP_XML_MIME
from envoy.server.model.server import RuntimeServerConfig
from envoy.server.model.subscription import Subscription, SubscriptionResource


@pytest.mark.anyio
async def test_create_site_controls_no_active_subscription(
    pg_base_config,
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
):
    uri = SiteControlUri.format(group_id=1)

    # There is currently a SiteControl sub in place - delete it before the test
    async with generate_async_session(pg_base_config) as session:
        select_result = await session.execute(select(Subscription).where(Subscription.subscription_id == 2))
        sub = select_result.scalar_one()
        await session.delete(sub)
        await session.commit()

    site_control_request_1 = generate_class_instance(SiteControlRequest)
    site_control_request_1.site_id = 1

    site_control_request_2 = generate_class_instance(SiteControlRequest, seed=123, optional_is_none=True)
    site_control_request_2.site_id = 2

    resp = await admin_client_auth.post(
        uri, content=f"[{site_control_request_1.model_dump_json()}, {site_control_request_2.model_dump_json()}]"
    )

    assert resp.status_code == HTTPStatus.CREATED

    assert not await notifications_enabled.wait_for_request(timeout_seconds=2)

    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0


@pytest.mark.anyio
async def test_create_site_controls_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests creating SiteControls with an active subscription generates notifications via the MockedAsyncClient"""
    uri = SiteControlUri.format(group_id=1)

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
                resource_type=SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
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
                resource_type=SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    control_1 = generate_class_instance(SiteControlRequest, seed=10001, site_id=1, calculation_log_id=None)
    control_2 = generate_class_instance(SiteControlRequest, seed=20002, site_id=1, calculation_log_id=1)
    control_3 = generate_class_instance(SiteControlRequest, seed=30003, site_id=2, calculation_log_id=1)
    control_4 = generate_class_instance(SiteControlRequest, seed=40004, site_id=3, calculation_log_id=None)

    content = ",".join([d.model_dump_json() for d in [control_1, control_2, control_3, control_4]])
    resp = await admin_client_auth.post(
        uri,
        content=f"[{content}]",
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=3, timeout_seconds=30)

    # Control 1,2 are batch 1 and go to sub1
    # Control 3 is batch 2 and go to sub1 and sub2
    # Control 4 is batch 3 and has no subscriptions (it belongs to a different aggregator)
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 3
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 2
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription2_uri)] == 1

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
                and f"{control_1.export_limit_watts}" in r.content
                and f"{control_2.export_limit_watts}" in r.content
                and f"{control_3.export_limit_watts}" not in r.content
                and f"{control_4.export_limit_watts}" not in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub 1) should have the doe1/doe2 batch"

    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri
                and f"{control_1.export_limit_watts}" not in r.content
                and f"{control_2.export_limit_watts}" not in r.content
                and f"{control_3.export_limit_watts}" in r.content
                and f"{control_4.export_limit_watts}" not in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub1) should have the doe3 batch"

    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription2_uri
                and f"{control_1.export_limit_watts}" not in r.content
                and f"{control_2.export_limit_watts}" not in r.content
                and f"{control_3.export_limit_watts}" in r.content
                and f"{control_4.export_limit_watts}" not in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub2) should have the doe3 batch"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_supersede_site_control_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests superseding a SiteControl with an active subscription generates notifications for the superseded and
    inserted entity"""

    uri = SiteControlUri.format(group_id=1)

    # Create a subscription to actually pickup these changes
    subscription1_uri = "http://my.example:542/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # this is unscoped
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
                resource_id=1,
                scoped_site_id=None,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # This will supersede DOE 1 and generate an insert for the new value
    # Use a small export_limit_watts to ensure it fits in Int16 when multiplied by 100 (pow10_multiplier=-2)
    control_1 = generate_class_instance(
        SiteControlRequest,
        seed=10001,
        site_id=1,
        calculation_log_id=None,
        start_time=datetime(2022, 5, 7, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        export_limit_watts=100,
    )

    content = ",".join([d.model_dump_json() for d in [control_1]])
    resp = await admin_client_auth.post(
        uri,
        content=f"[{content}]",
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

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
                and f"<value>{control_1.export_limit_watts * 100}</value>" in r.content  # Value of new DERControl
                and "<currentStatus>0</currentStatus>" in r.content  # One DERControl is "scheduled"
                and "<value>111</value>" in r.content  # Value of superseded DERControl
                and "<currentStatus>4</currentStatus>" in r.content  # One DERControl is "superseded"
                and "<status>0</status>" in r.content  # NotificationStatus DEFAULT
            ]
        )
        == 1
    ), "Only one notification for the insertion and superseded record"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_create_does_with_paginated_notifications(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
):
    """Tests creating SiteControls with an active subscription respected the subscription entity_limit"""
    uri = SiteControlUri.format(group_id=1)

    # Create a subscription to actually pickup these changes
    subscription1_uri = "http://my.example:542/uri"
    async with generate_async_session(pg_base_config) as session:
        # this is unscoped
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
                resource_id=None,
                scoped_site_id=None,
                notification_uri=subscription1_uri,
                entity_limit=2,
            )
        )

        await session.commit()

    control_1 = generate_class_instance(SiteControlRequest, seed=101, site_id=1, calculation_log_id=None)
    control_2 = generate_class_instance(SiteControlRequest, seed=202, site_id=1, calculation_log_id=None)
    control_3 = generate_class_instance(SiteControlRequest, seed=303, site_id=1, calculation_log_id=None)
    control_4 = generate_class_instance(SiteControlRequest, seed=404, site_id=3, calculation_log_id=None)

    content = ",".join([d.model_dump_json() for d in [control_1, control_2, control_3, control_4]])
    resp = await admin_client_auth.post(
        uri,
        content=f"[{content}]",
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=2, timeout_seconds=30)

    # We should get 2 pages of notifications despite them all belonging to the same batch
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 2
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 2

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
                if r.uri == subscription1_uri and 'results="2"' in r.content
            ]
        )
        == 1
    )

    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri and 'results="1"' in r.content
            ]
        )
        == 1
    )
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_create_tariff_component_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests creating tariff components with an active subscription generates notifications via the MockedAsyncClient"""

    # Create a subscription to actually pickup these changes
    #
    # We will create three subscriptions
    #   1) Subscribed to RateComponents on tariff 1 for site 1
    #   2) Subscribed to RateComponents on tariff 2 for site 1
    #   3) Subscribed to RateComponents on tariff 1 for site 2
    subscription1_uri = "http://example1:541/uri?a=b"
    subscription2_uri = "http://example2:542/uri?a=b"
    subscription3_uri = "http://example3:543/uri?a=b"
    async with generate_async_session(pg_base_config) as session:
        await session.execute(delete(Subscription))

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF_COMPONENT,
                resource_id=1,
                resource_parent_id=None,
                scoped_site_id=1,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF_COMPONENT,
                resource_id=2,
                resource_parent_id=None,
                scoped_site_id=1,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF_COMPONENT,
                resource_id=1,
                resource_parent_id=None,
                scoped_site_id=2,
                notification_uri=subscription3_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    tc_1 = generate_class_instance(TariffComponentRequest, seed=101, tariff_id=1, role_flags=1)
    resp = await admin_client_auth.post(TariffComponentCreateUri, content=tc_1.model_dump_json())
    assert resp.status_code == HTTPStatus.CREATED

    # Mismatches on tariff id - no notifications
    tc_2 = generate_class_instance(TariffComponentRequest, seed=303, tariff_id=3, role_flags=2)
    resp = await admin_client_auth.post(TariffComponentCreateUri, content=tc_2.model_dump_json())
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=2, timeout_seconds=30)

    # There will be 1 rate notification going out - one for sub1 and sub3 (matching tc_1)
    # RateComponents are NOT site scoped so they fire for all sites
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 2
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription3_uri)] == 1

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
                and "<roleFlags>01</roleFlags>" in r.content
                and "<roleFlags>02</roleFlags>" not in r.content
            ]
        )
        == 1
    ), "Only the tc_1 RateComponent should be sent out via notification for site1"
    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription3_uri
                and "<roleFlags>01</roleFlags>" in r.content
                and "<roleFlags>02</roleFlags>" not in r.content
            ]
        )
        == 1
    ), "Only the tc_1 RateComponent should be sent out via notification for site2"


@pytest.mark.anyio
async def test_create_tariff_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests creating tariffs with an active subscription generates notifications via the MockedAsyncClient"""

    # Create a subscription to actually pickup these changes
    #
    # We will create four subscriptions
    #   1) Subscribed to TariffProfiles for site 1 (no fsa_id)
    #   2) Subscribed to TariffProfiles for site 1 (fsa_id 1)
    subscription1_uri = "http://example1:541/uri?a=b"
    subscription2_uri = "http://example2:542/uri?a=b"
    async with generate_async_session(pg_base_config) as session:
        await session.execute(delete(Subscription))

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF,
                resource_id=None,
                resource_parent_id=None,
                scoped_site_id=1,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF,
                resource_id=1,
                resource_parent_id=None,
                scoped_site_id=1,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # Will match Sub 1/2
    t_1 = generate_class_instance(TariffRequest, seed=101, dnsp_code="mytariff1", fsa_id=1)
    resp = await admin_client_auth.post(TariffCreateUri, content=t_1.model_dump_json())
    assert resp.status_code == HTTPStatus.CREATED

    # Will only match Sub 1 (due to the fsa_id)
    t_2 = generate_class_instance(TariffRequest, seed=202, dnsp_code="mytariff2", fsa_id=2)
    resp = await admin_client_auth.post(TariffCreateUri, content=t_2.model_dump_json())
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=3, timeout_seconds=30)

    # There will be 1 rate notification going out - one for sub1 and sub3 (matching tc_1)
    # RateComponents are NOT site scoped so they fire for all sites
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 3
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 2
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription2_uri)] == 1

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
                and "<rateCode>mytariff1</rateCode>" in r.content
                and "<rateCode>mytariff2</rateCode>" not in r.content
            ]
        )
        == 1
    ), "Tariff 1 should be sent to sub1"
    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri
                and "<rateCode>mytariff1</rateCode>" not in r.content
                and "<rateCode>mytariff2</rateCode>" in r.content
            ]
        )
        == 1
    ), "Tariff 2 should be sent to sub1"
    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription2_uri
                and "<rateCode>mytariff1</rateCode>" in r.content
                and "<rateCode>mytariff2</rateCode>" not in r.content
            ]
        )
        == 1
    ), "Tariff 1 should be sent to sub2"


@pytest.mark.anyio
async def test_create_rates_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests creating rates with an active subscription generates notifications via the MockedAsyncClient"""

    # Create a subscription to actually pickup these changes
    #
    # We will create four subscriptions
    #   1) Subscribed to combined TTI's on tariff 1 for site 1
    #   2) Subscribed to RateComponent 1 TTI's for site 1
    #   3) Subscribed to combined TTI's on tariff 1 for site 2
    #   4) Subscribed to RateComponent 1 TTI's for site 2
    subscription1_uri = "http://example1:541/uri?a=b"
    subscription2_uri = "http://example2:542/uri?a=b"
    subscription3_uri = "http://example3:543/uri?a=b"
    subscription4_uri = "http://example4:544/uri?a=b"
    async with generate_async_session(pg_base_config) as session:
        await session.execute(delete(Subscription))

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.COMBINED_TARIFF_GENERATED_RATE,
                resource_id=1,
                resource_parent_id=None,
                scoped_site_id=1,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF_GENERATED_RATE,
                resource_id=1,
                resource_parent_id=1,
                scoped_site_id=1,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.COMBINED_TARIFF_GENERATED_RATE,
                resource_id=1,
                resource_parent_id=None,
                scoped_site_id=2,
                notification_uri=subscription3_uri,
                entity_limit=10,
            )
        )

        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF_GENERATED_RATE,
                resource_id=1,
                resource_parent_id=1,
                scoped_site_id=2,
                notification_uri=subscription4_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    rate_1 = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=101,
        site_id=1,
        tariff_component_id=1,
        start_time=datetime(2022, 3, 4, 14, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        calculation_log_id=1,
    )

    # Mismatches on site
    rate_2 = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=202,
        site_id=3,
        tariff_component_id=1,
        start_time=datetime(2022, 3, 4, 14, 5, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        calculation_log_id=None,
    )

    # Mismatches on rate component id
    rate_3 = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=303,
        site_id=1,
        tariff_component_id=4,
        start_time=datetime(2022, 3, 4, 14, 10, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        calculation_log_id=None,
    )

    content = ",".join([d.model_dump_json() for d in [rate_1, rate_2, rate_3]])
    resp = await admin_client_auth.post(TariffGeneratedRateCreateUri, content=f"[{content}]")
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=2, timeout_seconds=30)

    # There will be 2 price notifications going out - one for sub1 and one for sub2 (both matching rate1)
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 2
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription2_uri)] == 1

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
                and f"<price>{rate_1.price_pow10_encoded}</price>" in r.content
                and f"<price>{rate_2.price_pow10_encoded}</price>" not in r.content
                and f"<price>{rate_3.price_pow10_encoded}</price>" not in r.content
            ]
        )
        == 1
    ), "Only the rate1 price should be sent out via notification"

    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription2_uri
                and f"<price>{rate_1.price_pow10_encoded}</price>" in r.content
                and f"<price>{rate_2.price_pow10_encoded}</price>" not in r.content
                and f"<price>{rate_3.price_pow10_encoded}</price>" not in r.content
            ]
        )
        == 1
    ), "Only the rate1 price should be sent out via notification"


@pytest.mark.anyio
async def test_replace_rate_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests replacing rates with an active subscription generates notifications for the deleted and inserted entity"""
    # Create a subscription to actually pickup these changes
    subscription1_uri = "http://my.example:542/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # this is unscoped
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.TARIFF_GENERATED_RATE,
                resource_id=None,
                scoped_site_id=None,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # This will replace DOE 1 and generate a delete for the original and an insert for the new value
    rate_1 = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=10001,
        site_id=1,
        tariff_id=1,
        calculation_log_id=None,
        start_time=datetime(2022, 3, 5, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        import_active_price=91234,
        export_active_price=91235,
        import_reactive_price=91236,
        export_reactive_price=91237,
    )

    content = ",".join([d.model_dump_json() for d in [rate_1]])
    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{content}]",
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=8, timeout_seconds=30)

    # We get two notifications - but because these are prices, they get further split into import/export active/reactive
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 8  # One delete, One Changed, multiplied by 4
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 8

    assert all([HEADER_NOTIFICATION_ID in r.headers for r in notifications_enabled.logged_requests])
    assert len(set([r.headers[HEADER_NOTIFICATION_ID] for r in notifications_enabled.logged_requests])) == len(
        notifications_enabled.logged_requests
    ), "Expected unique notification ids for each request"

    # Do a really simple content check on the outgoing XML to ensure the notifications contain the expected
    # entities for each subscription
    for new_price in [
        rate_1.import_active_price,
        rate_1.export_active_price,
        rate_1.import_reactive_price,
        rate_1.export_reactive_price,
    ]:
        assert (
            len(
                [
                    r
                    for r in notifications_enabled.logged_requests
                    if r.uri == subscription1_uri and f"{new_price}" in r.content and "<status>0</status>" in r.content
                ]
            )
            == 1
        ), "Only one notification for the insertion"

    # prices from the original tariff_generated_rate that got deleted
    for original_price in [
        "cti/11",
        "cti/-122",
        "cti/1333",
        "cti/-14444",
    ]:
        assert (
            len(
                [
                    r
                    for r in notifications_enabled.logged_requests
                    if r.uri == subscription1_uri and original_price in r.content and "<status>4</status>" in r.content
                ]
            )
            == 1
        ), "Only one notification for the deletion"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_delete_site_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests delete sites with an active subscription generates notifications via the MockedAsyncClient"""
    # Create a subscription to actually pickup these changes
    subscription1_uri = "http://my.example:542/uri"
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

        await session.commit()

    # Delete site 1 and site 2
    resp = await admin_client_auth.delete(SiteUri.format(site_id=1))
    assert resp.status_code == HTTPStatus.NO_CONTENT

    resp = await admin_client_auth.delete(SiteUri.format(site_id=2))
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=2, timeout_seconds=30)

    # Sub 1 got both notifications
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 2
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 2

    assert all([HEADER_NOTIFICATION_ID in r.headers for r in notifications_enabled.logged_requests])
    assert len(set([r.headers[HEADER_NOTIFICATION_ID] for r in notifications_enabled.logged_requests])) == len(
        notifications_enabled.logged_requests
    ), "Expected unique notification ids for each request"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_update_server_config_edev_list_notification(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests that updating server config generates subscription notifications for EndDeviceList"""

    subscription1_uri = "http://my.example:542/uri"

    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # Will pickup site notifications
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
        await session.commit()

    # Update edev list config
    edev_list_poll_rate = 131009115
    config_request = generate_class_instance(
        RuntimeServerConfigRequest, optional_is_none=True, edevl_pollrate_seconds=edev_list_poll_rate
    )
    resp = await admin_client_auth.post(ServerConfigRuntimeUri, content=config_request.model_dump_json())
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

    # Sub 1 got one notification, sub 2 got the other
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1

    assert all([HEADER_NOTIFICATION_ID in r.headers for r in notifications_enabled.logged_requests])
    assert len(set([r.headers[HEADER_NOTIFICATION_ID] for r in notifications_enabled.logged_requests])) == len(
        notifications_enabled.logged_requests
    ), "Expected unique notification ids for each request"
    assert f'pollRate="{edev_list_poll_rate}"' in notifications_enabled.logged_requests[0].content
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_update_server_config_fsa_notification(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests that updating server config generates subscription notifications for FSA list"""

    subscription1_uri = "http://my.example:542/uri"
    subscription2_uri = "https://my.other.example:542/uri"

    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # Will pickup FSA notifications for site 2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        # Will pickup FSA notifications for site 3
        await session.execute(
            insert(Subscription).values(
                aggregator_id=2,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
                resource_id=None,
                scoped_site_id=3,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # Update fsa config
    config_request = generate_class_instance(RuntimeServerConfigRequest, seed=101, disable_edev_registration=True)
    resp = await admin_client_auth.post(ServerConfigRuntimeUri, content=config_request.model_dump_json())
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=2, timeout_seconds=30)

    # Sub 1 got one notification, sub 2 got the other
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 2
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription2_uri)] == 1

    assert all([HEADER_NOTIFICATION_ID in r.headers for r in notifications_enabled.logged_requests])
    assert len(set([r.headers[HEADER_NOTIFICATION_ID] for r in notifications_enabled.logged_requests])) == len(
        notifications_enabled.logged_requests
    ), "Expected unique notification ids for each request"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.parametrize("none_fsa_value", [True, False])
@pytest.mark.anyio
async def test_update_server_config_fsa_notification_no_change(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config, none_fsa_value: bool
):
    """Tests that updating server config (with no changed value for FSA) generates 0 notifications"""

    subscription1_uri = "http://my.example:542/uri"
    fsa_poll_rate = 123

    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # Force the server FSA pollrate config to a known value
        await session.execute(delete(RuntimeServerConfig))
        await session.execute(
            insert(RuntimeServerConfig).values(
                changed_time=datetime.now(),
                dcap_pollrate_seconds=None,
                edevl_pollrate_seconds=None,
                fsal_pollrate_seconds=fsa_poll_rate,
                derpl_pollrate_seconds=None,
                derl_pollrate_seconds=None,
                mup_postrate_seconds=None,
                site_control_pow10_encoding=None,
                disable_edev_registration=False,
            )
        )

        # Will pickup FSA notifications for site 2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # Update config with the subscriptions now live
    config_request = generate_class_instance(
        RuntimeServerConfigRequest,
        optional_is_none=True,
        disable_edev_registration=True,
        fsal_pollrate_seconds=None if none_fsa_value else fsa_poll_rate,
    )
    resp = await admin_client_auth.post(ServerConfigRuntimeUri, content=config_request.model_dump_json())
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give any notifications a chance to propagate
    await asyncio.sleep(3)

    # No notifications should've been generated as we aren't actually changing any values associated with the FSA
    assert len(notifications_enabled.logged_requests) == 0


@pytest.mark.anyio
async def test_update_site_control_group_default_notification(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests that updating site control group default generates subscription notifications for DefaultDERControl"""

    subscription1_uri = "http://my.example:542/uri"

    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # Will pickup default updates for site 2, derp 3
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.DEFAULT_SITE_CONTROL,
                resource_id=3,
                scoped_site_id=2,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # now do an update for certain fields
    config_request = SiteControlGroupDefaultRequest(
        import_limit_watts=UpdateDefaultValue(value=None),
        export_limit_watts=UpdateDefaultValue(value=Decimal("2.34")),
        generation_limit_watts=None,
        load_limit_watts=None,
        ramp_rate_percent_per_second=None,
    )

    # Update default controls for DERP2 and DERP3
    resp = await admin_client_auth.post(
        SiteControlGroupDefaultUri.format(group_id=2), content=config_request.model_dump_json()
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT

    resp = await admin_client_auth.post(
        SiteControlGroupDefaultUri.format(group_id=3), content=config_request.model_dump_json()
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

    # Only one request should've generated a notification
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1


@pytest.mark.anyio
async def test_create_site_control_groups_with_active_subscription(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
):
    """Tests creating site control requests with an active subscription generates notifications via MockedAsyncClient"""

    # Create a subscription to actually pickup these changes
    subscription2_uri = "https://my.other.example:542/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # This is scoped to site2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.SITE_CONTROL_GROUP,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription2_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    primacy = 49
    site_control_request = SiteControlGroupRequest(description="new group", primacy=primacy)

    resp = await admin_client_auth.post(
        SiteControlGroupListUri,
        content=site_control_request.model_dump_json(),
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

    # SiteControlGroup changes generate 1 notification per site. That means:
    # sub1: Will get 3 notification batch (site 1, 2 and 4 - all under agg 1)
    # sub2: Will get 1 notification batch (it's scoped to just site 2)
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription2_uri)] == 1

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
                if r.uri == subscription2_uri
                and str(primacy) in r.content
                and "/edev/1/" not in r.content
                and "/edev/2/derp/5" in r.content
                and "/edev/4/" not in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub 2) should be for the new DERP (id 3) for site 2"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_create_site_control_groups_with_new_fsa(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
):
    """Tests creating site control groups with a new FunctionSetAssignment ID generates notifications for FSA subs
    via MockedAsyncClient"""

    # Create a subscription to actually pickup these changes
    subscription1_uri = "https://my.example:123/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # This is scoped to site2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    primacy = 76
    fsa_id = 19341
    site_control_request = SiteControlGroupRequest(description="new group", primacy=primacy, fsa_id=fsa_id)

    resp = await admin_client_auth.post(
        SiteControlGroupListUri,
        content=site_control_request.model_dump_json(),
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 1

    assert all([HEADER_NOTIFICATION_ID in r.headers for r in notifications_enabled.logged_requests])
    assert len(set([r.headers[HEADER_NOTIFICATION_ID] for r in notifications_enabled.logged_requests])) == len(
        notifications_enabled.logged_requests
    ), "Expected unique notification ids for each request"

    # Do a really simple content check on the outgoing XML to ensure the notifications contain the expected
    # FSA entities for each subscription
    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri
                and "</FunctionSetAssignments>" in r.content
                and f"/edev/1/fsa/{fsa_id}" not in r.content
                and f"/edev/2/fsa/{fsa_id}" in r.content
                and f"/edev/4/fsa/{fsa_id}" not in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub 2) should be for the new FSA for site 2"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])


@pytest.mark.anyio
async def test_create_site_control_groups_no_new_fsa(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
):
    """Tests creating site control groups with a an existing FunctionSetAssignment ID skips notifications for FSA subs
    via MockedAsyncClient"""

    # Create a subscription to actually pickup these changes
    subscription1_uri = "https://my.example:123/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # This is scoped to site2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    primacy = 76
    fsa_id = 1  # Already exists
    site_control_request = SiteControlGroupRequest(description="new group", primacy=primacy, fsa_id=fsa_id)

    resp = await admin_client_auth.post(
        SiteControlGroupListUri,
        content=site_control_request.model_dump_json(),
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give any notifications a chance to propagate
    await asyncio.sleep(2)

    assert (
        len(notifications_enabled.logged_requests) == 0
    ), "This is NOT a new fsa_id - There shouldn't be a notification"


@pytest.mark.anyio
async def test_update_site_with_active_subscription(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
):
    """Tests updates to sites with an active subscription generates notifications via MockedAsyncClient"""

    # Create a subscription to actually pickup these changes
    subscription2_uri = "https://my.other.example:542/uri"
    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

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

    post_rate_seconds = 12344321
    update_request = SiteUpdateRequest(
        post_rate_seconds=post_rate_seconds, nmi=None, timezone_id=None, device_category=None
    )

    resp = await admin_client_auth.post(
        SiteUri.format(site_id=2),
        content=update_request.model_dump_json(),
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=1, timeout_seconds=30)

    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 1
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription2_uri)] == 1

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
                if r.uri == subscription2_uri and str(post_rate_seconds) in r.content and "/edev/2" in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub 2) should be for site 2"
    assert all([r.headers.get("Content-Type") == SEP_XML_MIME for r in notifications_enabled.logged_requests])
