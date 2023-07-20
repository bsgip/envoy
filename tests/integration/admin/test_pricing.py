import json
from http import HTTPStatus

import pytest
from envoy_schema.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest, TariffResponse
from envoy_schema.admin.schema.uri import TariffCreateUri, TariffGeneratedRateCreateUri, TariffUpdateUri
from httpx import AsyncClient

from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


@pytest.mark.anyio
async def test_get_all_tariffs(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(TariffCreateUri, params={"limit": 3})
    assert resp.status_code == HTTPStatus.OK
    tariff_resp_list = [TariffResponse(**d) for d in json.loads(resp.content)]
    assert len(tariff_resp_list) == 3


@pytest.mark.anyio
async def test_get_single_tariff(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(TariffUpdateUri.format(tariff_id=1))
    assert resp.status_code == HTTPStatus.OK
    tariff_resp = TariffResponse(**json.loads(resp.content))
    assert tariff_resp.tariff_id == 1


@pytest.mark.anyio
async def test_create_tariff(admin_client_auth: AsyncClient):
    tariff = generate_class_instance(TariffRequest)
    tariff.currency_code = 36
    resp = await admin_client_auth.post(TariffCreateUri, json=tariff.dict())

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.anyio
async def test_update_tariff(admin_client_auth: AsyncClient):
    tariff = generate_class_instance(TariffRequest)
    tariff.currency_code = 36
    resp = await admin_client_auth.put(TariffUpdateUri.format(tariff_id=1), json=tariff.dict())

    assert resp.status_code == HTTPStatus.OK


@pytest.mark.anyio
async def test_create_tariff_genrates(admin_client_auth: AsyncClient):
    tariff_genrate = generate_class_instance(TariffGeneratedRateRequest)
    tariff_genrate.tariff_id = 1
    tariff_genrate.site_id = 1

    tariff_genrate_1 = generate_class_instance(TariffGeneratedRateRequest)
    tariff_genrate_1.tariff_id = 2
    tariff_genrate_1.site_id = 2

    resp = await admin_client_auth.post(
        TariffGeneratedRateCreateUri, content=f"[{tariff_genrate.json()}, {tariff_genrate_1.json()}]"
    )

    assert resp.status_code == HTTPStatus.CREATED
