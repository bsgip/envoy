import json
from http import HTTPStatus

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.config import RuntimeServerConfigRequest, RuntimeServerConfigResponse
from envoy_schema.admin.schema.uri import ServerConfigRuntimeUri
from httpx import AsyncClient
from sqlalchemy import delete, select

from envoy.server.model.archive.server import ArchiveRuntimeServerConfig
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
    assert config_response.disable_edev_registration is False

    # Update some config
    config_request = generate_class_instance(RuntimeServerConfigRequest, seed=101, disable_edev_registration=True)
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

    # first-ever creation shouldn't archive anything (there was no existing row to snapshot)
    async with generate_async_session(pg_base_config) as session:
        archived = (await session.execute(select(ArchiveRuntimeServerConfig))).scalars().all()
        assert len(archived) == 0

    # update again (this time there is something in the db)
    second_config_request = generate_class_instance(
        RuntimeServerConfigRequest, seed=202, disable_edev_registration=False
    )
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

    # the pre-update (first) values should now be archived
    async with generate_async_session(pg_base_config) as session:
        archived = (await session.execute(select(ArchiveRuntimeServerConfig))).scalars().all()
        assert len(archived) == 1
        assert archived[0].mup_postrate_seconds == config_request.mup_postrate_seconds
        assert archived[0].disable_edev_registration == config_request.disable_edev_registration
        assert archived[0].deleted_time is None

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
    assert third_update_response.site_control_pow10_encoding == third_config_request.site_control_pow10_encoding, (
        "This was the updated field"
    )

    # the second update's pre-update values should now also be archived
    async with generate_async_session(pg_base_config) as session:
        archived = (await session.execute(select(ArchiveRuntimeServerConfig))).scalars().all()
        assert len(archived) == 2
        assert archived[1].mup_postrate_seconds == second_config_request.mup_postrate_seconds
        assert archived[1].site_control_pow10_encoding == second_config_request.site_control_pow10_encoding
