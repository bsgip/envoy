from asyncio import sleep
from http import HTTPStatus
from typing import Sequence

import pytest
from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest
from envoy_schema.admin.schema.uri import DoeCreateUri
from httpx import AsyncClient
from sqlalchemy import select

from envoy.server.model.subscription import Subscription, SubscriptionResource
from tests.data.fake.generator import generate_class_instance
from tests.postgres_testing import generate_async_session
from tests.unit.mocks import MockedAsyncClient


@pytest.mark.anyio
async def test_create_does(admin_client_auth: AsyncClient):
    doe = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe.site_id = 1

    doe_1 = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(DoeCreateUri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.anyio
async def test_create_does_no_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient
):
    doe = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe.site_id = 1

    doe_1 = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(DoeCreateUri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED

    await sleep(0.5)

    assert notifications_enabled.post_calls == 0


@pytest.mark.anyio
async def test_create_does_with_active_subscription(
    admin_client_auth: AsyncClient, notifications_enabled: MockedAsyncClient, pg_base_config
):
    # Modify a subscription to actually pickup these changes
    async with generate_async_session(pg_base_config) as session:
        all_entities_resp = await session.execute(select(Subscription))
        all_entities: Sequence[Subscription] = all_entities_resp.scalars().all()

        all_entities[0].resource_type = SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE
        all_entities[0].scoped_site_id = None
        all_entities[0].resource_id = None

        await session.commit()

    doe = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe.site_id = 1

    doe_1 = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(DoeCreateUri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED

    await sleep(1)

    assert notifications_enabled.post_calls == 1
