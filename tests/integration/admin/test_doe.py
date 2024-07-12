from http import HTTPStatus

import pytest
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest
from envoy_schema.admin.schema.uri import DoeCreateUri
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_does(admin_client_auth: AsyncClient):
    doe = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe.site_id = 1

    doe_1 = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(DoeCreateUri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED
