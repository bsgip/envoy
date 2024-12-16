from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.http import HTTPMethod, MockedAsyncClient
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest
from envoy_schema.admin.schema.pricing import TariffGeneratedRateRequest
from envoy_schema.admin.schema.uri import DoeUri, TariffGeneratedRateCreateUri
from httpx import AsyncClient
from sqlalchemy import delete, insert, select

from envoy.notification.task.transmit import HEADER_NOTIFICATION_ID
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import PRICE_DECIMAL_POWER


@pytest.mark.anyio
async def test_create_does_no_active_subscription(
    pg_base_config, admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient
):
    # There is currently a DOE sub in place - delete it before the test
    async with generate_async_session(pg_base_config) as session:
        select_result = await session.execute(select(Subscription).where(Subscription.subscription_id == 2))
        sub = select_result.scalar_one()
        await session.delete(sub)
        await session.commit()

    doe = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe.site_id = 1

    doe_1 = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(DoeUri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED

    assert not await notifications_enabled.wait_for_request(timeout_seconds=2)

    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0


@pytest.mark.anyio
async def test_create_does_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests creating DOEs with an active subscription generates notifications via the MockedAsyncClient"""
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

    doe_1: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=10001, site_id=1, calculation_log_id=None
    )
    doe_2: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=20002, site_id=1, calculation_log_id=1
    )
    doe_3: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=30003, site_id=2, calculation_log_id=1
    )
    doe_4: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=40004, site_id=3, calculation_log_id=None
    )

    content = ",".join([d.model_dump_json() for d in [doe_1, doe_2, doe_3, doe_4]])
    resp = await admin_client_auth.post(
        DoeUri,
        content=f"[{content}]",
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=3, timeout_seconds=30)

    # DOE 1,2 are batch 1 and go to sub1
    # DOE 3 is batch 2 and go to sub1 and sub2
    # DOE 4 is batch 3 and has no subscriptions (it belongs to a different aggregator)
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
                and f"{doe_1.export_limit_watts}" in r.content
                and f"{doe_2.export_limit_watts}" in r.content
                and f"{doe_3.export_limit_watts}" not in r.content
                and f"{doe_4.export_limit_watts}" not in r.content
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
                and f"{doe_1.export_limit_watts}" not in r.content
                and f"{doe_2.export_limit_watts}" not in r.content
                and f"{doe_3.export_limit_watts}" in r.content
                and f"{doe_4.export_limit_watts}" not in r.content
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
                and f"{doe_1.export_limit_watts}" not in r.content
                and f"{doe_2.export_limit_watts}" not in r.content
                and f"{doe_3.export_limit_watts}" in r.content
                and f"{doe_4.export_limit_watts}" not in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub2) should have the doe3 batch"


@pytest.mark.anyio
async def test_replace_doe_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests replacing a DOEs with an active subscription generates notifications for the deleted and inserted entity"""
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
                resource_id=None,
                scoped_site_id=None,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # This will replace DOE 1 and generate a delete for the original and an insert for the new value
    doe_1: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest,
        seed=10001,
        site_id=1,
        calculation_log_id=None,
        start_time=datetime(2022, 5, 7, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
    )

    content = ",".join([d.model_dump_json() for d in [doe_1]])
    resp = await admin_client_auth.post(
        DoeUri,
        content=f"[{content}]",
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=2, timeout_seconds=30)

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
                if r.uri == subscription1_uri
                and f"{doe_1.export_limit_watts}" in r.content
                and "<status>0</status>" in r.content
            ]
        )
        == 1
    ), "Only one notification for the insertion"

    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri
                and "<value>111</value>" in r.content
                and "<status>4</status>" in r.content
            ]
        )
        == 1
    ), "Only one notification for the deletion"


@pytest.mark.anyio
async def test_create_does_with_paginated_notifications(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests creating DOEs with an active subscription respected the subscription entity_limit"""
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

    doe_1: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=101, site_id=1, calculation_log_id=None
    )
    doe_2: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=202, site_id=1, calculation_log_id=None
    )
    doe_3: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=303, site_id=1, calculation_log_id=None
    )
    doe_4: DynamicOperatingEnvelopeRequest = generate_class_instance(
        DynamicOperatingEnvelopeRequest, seed=404, site_id=3, calculation_log_id=None
    )

    content = ",".join([d.model_dump_json() for d in [doe_1, doe_2, doe_3, doe_4]])
    resp = await admin_client_auth.post(
        DoeUri,
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


@pytest.mark.anyio
async def test_create_rates_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests creating rates with an active subscription generates notifications via the MockedAsyncClient"""
    # Create a subscription to actually pickup these changes
    subscription1_uri = "http://example:542/uri?a=b"
    async with generate_async_session(pg_base_config) as session:
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

    rate_1: TariffGeneratedRateRequest = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=101,
        site_id=1,
        tariff_id=1,
        start_time=datetime(2022, 3, 4, 14, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        calculation_log_id=1,
    )

    rate_2: TariffGeneratedRateRequest = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=202,
        site_id=1,
        tariff_id=1,
        start_time=datetime(2022, 3, 4, 14, 5, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        calculation_log_id=None,
    )

    rate_3: TariffGeneratedRateRequest = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=303,
        site_id=1,
        tariff_id=1,
        start_time=datetime(2022, 3, 4, 14, 10, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        calculation_log_id=None,
    )

    rate_4: TariffGeneratedRateRequest = generate_class_instance(
        TariffGeneratedRateRequest,
        seed=404,
        site_id=3,
        tariff_id=1,
        start_time=datetime(2022, 3, 4, 14, 15, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        calculation_log_id=None,
    )

    content = ",".join([d.model_dump_json() for d in [rate_1, rate_2, rate_3, rate_4]])
    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri,
        content=f"[{content}]",
    )
    assert resp.status_code == HTTPStatus.CREATED

    # Give the notifications a chance to propagate
    assert await notifications_enabled.wait_for_n_requests(n=4, timeout_seconds=30)

    # There will be 4 price notifications going out (one for each price type)
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 4
    assert notifications_enabled.call_count_by_method_uri[(HTTPMethod.POST, subscription1_uri)] == 4

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
                and f"/{int(rate_1.export_active_price * PRICE_DECIMAL_POWER)}" in r.content
                and f"/{int(rate_2.export_active_price * PRICE_DECIMAL_POWER)}" in r.content
                and f"/{int(rate_3.export_active_price * PRICE_DECIMAL_POWER)}" in r.content
                and f"/{int(rate_4.export_active_price * PRICE_DECIMAL_POWER)}" not in r.content
            ]
        )
        == 1
    ), "Only one notification should have the export prices"

    assert (
        len(
            [
                r
                for r in notifications_enabled.logged_requests
                if r.uri == subscription1_uri
                and f"/{int(rate_1.import_active_price * PRICE_DECIMAL_POWER)}" in r.content
                and f"/{int(rate_2.import_active_price * PRICE_DECIMAL_POWER)}" in r.content
                and f"/{int(rate_3.import_active_price * PRICE_DECIMAL_POWER)}" in r.content
                and f"/{int(rate_4.import_active_price * PRICE_DECIMAL_POWER)}" not in r.content
            ]
        )
        == 1
    ), "Only one notification should have the import prices"


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
