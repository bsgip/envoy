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
from envoy_schema.admin.schema.config import ControlDefaultRequest, RuntimeServerConfigRequest, UpdateDefaultValue
from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest
from envoy_schema.admin.schema.pricing import TariffGeneratedRateRequest
from envoy_schema.admin.schema.site import SiteUpdateRequest
from envoy_schema.admin.schema.site_control import SiteControlGroupRequest, SiteControlRequest
from envoy_schema.admin.schema.uri import (
    DoeUri,
    ServerConfigRuntimeUri,
    SiteControlDefaultConfigUri,
    SiteControlGroupListUri,
    SiteControlUri,
    SiteUri,
    TariffGeneratedRateCreateUri,
)
from httpx import AsyncClient
from sqlalchemy import delete, insert, select

from envoy.notification.task.transmit import HEADER_NOTIFICATION_ID
from envoy.server.model.server import RuntimeServerConfig
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import PRICE_DECIMAL_POWER


@pytest.mark.parametrize(
    "body_type, uri",
    [(DynamicOperatingEnvelopeRequest, DoeUri), (SiteControlRequest, SiteControlUri.format(group_id=1))],
)
@pytest.mark.anyio
async def test_create_does_no_active_subscription(
    pg_base_config,
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    body_type: Union[type[DynamicOperatingEnvelopeRequest], type[SiteControlRequest]],
    uri: str,
):
    # There is currently a DOE sub in place - delete it before the test
    async with generate_async_session(pg_base_config) as session:
        select_result = await session.execute(select(Subscription).where(Subscription.subscription_id == 2))
        sub = select_result.scalar_one()
        await session.delete(sub)
        await session.commit()

    doe = generate_class_instance(body_type)
    doe.site_id = 1

    doe_1 = generate_class_instance(body_type, seed=123, optional_is_none=True)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(uri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED

    assert not await notifications_enabled.wait_for_request(timeout_seconds=2)

    assert notifications_enabled.call_count_by_method[HTTPMethod.POST] == 0
    assert notifications_enabled.call_count_by_method[HTTPMethod.GET] == 0


@pytest.mark.parametrize(
    "body_type, uri",
    [(DynamicOperatingEnvelopeRequest, DoeUri), (SiteControlRequest, SiteControlUri.format(group_id=1))],
)
@pytest.mark.anyio
async def test_create_does_with_active_subscription(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
    body_type: Union[type[DynamicOperatingEnvelopeRequest], type[SiteControlRequest]],
    uri: str,
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

    doe_1 = generate_class_instance(body_type, seed=10001, site_id=1, calculation_log_id=None)
    doe_2 = generate_class_instance(body_type, seed=20002, site_id=1, calculation_log_id=1)
    doe_3 = generate_class_instance(body_type, seed=30003, site_id=2, calculation_log_id=1)
    doe_4 = generate_class_instance(body_type, seed=40004, site_id=3, calculation_log_id=None)

    content = ",".join([d.model_dump_json() for d in [doe_1, doe_2, doe_3, doe_4]])
    resp = await admin_client_auth.post(
        uri,
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


@pytest.mark.parametrize(
    "body_type, uri",
    [(DynamicOperatingEnvelopeRequest, DoeUri), (SiteControlRequest, SiteControlUri.format(group_id=1))],
)
@pytest.mark.anyio
async def test_supersede_doe_with_active_subscription(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
    body_type: Union[type[DynamicOperatingEnvelopeRequest], type[SiteControlRequest]],
    uri: str,
):
    """Tests superseding a DOE with an active subscription generates notifications for the superseded and inserted
    entity"""

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
    doe_1 = generate_class_instance(
        body_type,
        seed=10001,
        site_id=1,
        calculation_log_id=None,
        start_time=datetime(2022, 5, 7, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
    )

    content = ",".join([d.model_dump_json() for d in [doe_1]])
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
                and f"<value>{doe_1.export_limit_watts * 100}</value>" in r.content  # Value of new DERControl
                and "<currentStatus>0</currentStatus>" in r.content  # One DERControl is "scheduled"
                and "<value>111</value>" in r.content  # Value of superseded DERControl
                and "<currentStatus>4</currentStatus>" in r.content  # One DERControl is "superseded"
                and "<status>0</status>" in r.content  # NotificationStatus DEFAULT
            ]
        )
        == 1
    ), "Only one notification for the insertion and superseded record"


@pytest.mark.parametrize(
    "body_type, uri",
    [(DynamicOperatingEnvelopeRequest, DoeUri), (SiteControlRequest, SiteControlUri.format(group_id=1))],
)
@pytest.mark.anyio
async def test_create_does_with_paginated_notifications(
    admin_client_auth: AsyncClient,
    notifications_enabled: MockedAsyncClient,
    pg_base_config,
    body_type: Union[type[DynamicOperatingEnvelopeRequest], type[SiteControlRequest]],
    uri: str,
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

    doe_1 = generate_class_instance(body_type, seed=101, site_id=1, calculation_log_id=None)
    doe_2 = generate_class_instance(body_type, seed=202, site_id=1, calculation_log_id=None)
    doe_3 = generate_class_instance(body_type, seed=303, site_id=1, calculation_log_id=None)
    doe_4 = generate_class_instance(body_type, seed=404, site_id=3, calculation_log_id=None)

    content = ",".join([d.model_dump_json() for d in [doe_1, doe_2, doe_3, doe_4]])
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
async def test_update_site_default_config_notification(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    """Tests that updating site default config generates subscription notifications for DefaultDERControl"""

    subscription1_uri = "http://my.example:542/uri"

    async with generate_async_session(pg_base_config) as session:
        # Clear any other subs first
        await session.execute(delete(Subscription))

        # Will pickup site default updates for site 2
        await session.execute(
            insert(Subscription).values(
                aggregator_id=1,
                changed_time=datetime.now(),
                resource_type=SubscriptionResource.DEFAULT_SITE_CONTROL,
                resource_id=None,
                scoped_site_id=2,
                notification_uri=subscription1_uri,
                entity_limit=10,
            )
        )

        await session.commit()

    # now do an update for certain fields
    config_request = ControlDefaultRequest(
        import_limit_watts=UpdateDefaultValue(value=None),
        export_limit_watts=UpdateDefaultValue(value=Decimal("2.34")),
        generation_limit_watts=None,
        load_limit_watts=None,
        ramp_rate_percent_per_second=None,
    )

    # Update default controls for site 1 and site 2
    resp = await admin_client_auth.post(
        SiteControlDefaultConfigUri.format(site_id=1), content=config_request.model_dump_json()
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT

    resp = await admin_client_auth.post(
        SiteControlDefaultConfigUri.format(site_id=2), content=config_request.model_dump_json()
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
                and "/edev/1/derp/3" not in r.content
                and "/edev/2/derp/3" in r.content
                and "/edev/4/derp/3" not in r.content
            ]
        )
        == 1
    ), "Only one notification (for sub 2) should be for the new DERP (id 3) for site 2"


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
