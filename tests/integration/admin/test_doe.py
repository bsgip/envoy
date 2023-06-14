import pytest

from http import HTTPStatus
from httpx import AsyncClient

from envoy.admin.schema.doe import DynamicOperatingEnvelopeRequest
from envoy.admin.schema.uri import DoeCreateUri

from tests.data.fake.generator import generate_class_instance, assert_class_instance_equality


@pytest.mark.anyio
async def test_create_tariff_genrates(admin_client_auth: AsyncClient):
    doe = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe.site_id = 1

    doe_1 = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(DoeCreateUri, content=f"[{doe.json()}, {doe_1.json()}]")

    assert resp.status_code == HTTPStatus.CREATED
