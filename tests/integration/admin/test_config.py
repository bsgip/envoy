import json
from decimal import Decimal
from http import HTTPStatus
from typing import Optional

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.config import (
    ControlDefaultRequest,
    ControlDefaultResponse,
    RuntimeServerConfigRequest,
    RuntimeServerConfigResponse,
    UpdateDefaultValue,
)
from envoy_schema.admin.schema.uri import ServerConfigRuntimeUri, SiteControlDefaultConfigUri
from httpx import AsyncClient
from sqlalchemy import delete

from envoy.server.model.server import RuntimeServerConfig
from tests.integration.response import read_response_body_string


@pytest.mark.anyio
async def test_get_update_server_config(admin_client_auth: AsyncClient, pg_base_config):
    """Tests that server config can be created and then fetched"""

    # Start by wiping config
    async with generate_async_session(pg_base_config) as session:
        await session.execute(delete(RuntimeServerConfig))
        await session.commit()

    # We should fetch default now
    resp = await admin_client_auth.get(ServerConfigRuntimeUri)
    assert resp.status_code == HTTPStatus.OK
    body = read_response_body_string(resp)
    config_response: RuntimeServerConfigResponse = RuntimeServerConfigResponse(**json.loads(body))
    assert config_response.dcap_pollrate_seconds > 0
    assert config_response.derpl_pollrate_seconds > 0

    # Update some config
    config_request = generate_class_instance(RuntimeServerConfigRequest, seed=101)
    resp = await admin_client_auth.post(ServerConfigRuntimeUri, content=config_request.model_dump_json())
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Now refetch
    resp = await admin_client_auth.get(ServerConfigRuntimeUri)
    assert resp.status_code == HTTPStatus.OK
    body = read_response_body_string(resp)
    first_update_response: RuntimeServerConfigResponse = RuntimeServerConfigResponse(**json.loads(body))

    assert_nowish(first_update_response.changed_time)
    assert_nowish(first_update_response.created_time)
    assert_class_instance_equality(
        RuntimeServerConfigRequest, config_request, first_update_response, {"tariff_pow10_encoding"}
    )

    # update again (this time there is something in the db)
    second_config_request = generate_class_instance(RuntimeServerConfigRequest, seed=202)
    resp = await admin_client_auth.post(ServerConfigRuntimeUri, content=second_config_request.model_dump_json())
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Now refetch
    resp = await admin_client_auth.get(ServerConfigRuntimeUri)
    assert resp.status_code == HTTPStatus.OK
    body = read_response_body_string(resp)
    second_update_response: RuntimeServerConfigResponse = RuntimeServerConfigResponse(**json.loads(body))

    assert_class_instance_equality(
        RuntimeServerConfigRequest, second_config_request, second_update_response, {"tariff_pow10_encoding"}
    )

    # update again - but only one field
    third_config_request = generate_class_instance(RuntimeServerConfigRequest, seed=303, optional_is_none=True)
    third_config_request.site_control_pow10_encoding = 11
    resp = await admin_client_auth.post(ServerConfigRuntimeUri, content=third_config_request.model_dump_json())
    assert resp.status_code == HTTPStatus.NO_CONTENT

    # Now refetch
    resp = await admin_client_auth.get(ServerConfigRuntimeUri)
    assert resp.status_code == HTTPStatus.OK
    body = read_response_body_string(resp)
    third_update_response: RuntimeServerConfigResponse = RuntimeServerConfigResponse(**json.loads(body))

    # Should be the same as the second query (but our changed field has updated)
    assert_class_instance_equality(
        RuntimeServerConfigRequest,
        second_config_request,
        third_update_response,
        {"tariff_pow10_encoding", "site_control_pow10_encoding"},
    )
    assert (
        third_update_response.site_control_pow10_encoding == third_config_request.site_control_pow10_encoding
    ), "This was the updated field"


@pytest.mark.parametrize(
    "site_id, expected",
    [
        (1, (Decimal("10.10"), Decimal("9.99"), Decimal("8.88"), Decimal("7.77"))),
        (2, (None, None, None, None)),
        (3, (Decimal("20.20"), Decimal("19.19"), Decimal("18.18"), Decimal("17.17"))),
        (5, (None, None, None, None)),
        (6, (None, None, None, None)),
        (99, None),
    ],
)
@pytest.mark.anyio
async def test_get_and_update_site_control_default(
    admin_client_auth: AsyncClient, site_id: int, expected: Optional[tuple]
):
    resp = await admin_client_auth.get(SiteControlDefaultConfigUri.format(site_id=site_id))
    if expected is None:
        assert resp.status_code == HTTPStatus.NOT_FOUND
    else:
        assert resp.status_code == HTTPStatus.OK
        body = read_response_body_string(resp)
        config: ControlDefaultResponse = ControlDefaultResponse(**json.loads(body))
        assert expected == (
            config.server_default_import_limit_watts,
            config.server_default_export_limit_watts,
            config.server_default_generation_limit_watts,
            config.server_default_load_limit_watts,
        )

    # now do an update for certain fields
    config_request = ControlDefaultRequest(
        import_limit_watts=UpdateDefaultValue(value=None),
        export_limit_watts=UpdateDefaultValue(value=Decimal("1.11")),
        generation_limit_watts=None,
        load_limit_watts=None,
        ramp_rate_percent_per_second=None,
    )
    resp = await admin_client_auth.post(
        SiteControlDefaultConfigUri.format(site_id=site_id), content=config_request.model_dump_json()
    )
    if not expected:
        assert resp.status_code == HTTPStatus.NOT_FOUND
    else:
        assert resp.status_code == HTTPStatus.NO_CONTENT

    # and refetch
    resp = await admin_client_auth.get(SiteControlDefaultConfigUri.format(site_id=site_id))

    # Make sure only the fields we updated did an update
    if expected is None:
        assert resp.status_code == HTTPStatus.NOT_FOUND
    else:
        assert resp.status_code == HTTPStatus.OK
        body = read_response_body_string(resp)
        config: ControlDefaultResponse = ControlDefaultResponse(**json.loads(body))

        assert (None, Decimal("1.11"), expected[2], expected[3]) == (
            config.server_default_import_limit_watts,
            config.server_default_export_limit_watts,
            config.server_default_generation_limit_watts,
            config.server_default_load_limit_watts,
        )
