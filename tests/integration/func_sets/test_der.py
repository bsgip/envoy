from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import pytest
from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.der import (
    DER,
    DERAvailability,
    DERCapability,
    DERListResponse,
    DERSettings,
    DERStatus,
)
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.manager.der import PUBLIC_SITE_DER_ID
from envoy.server.model.site import SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from tests.assert_time import assert_nowish
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance
from tests.integration.request import build_paging_params
from tests.integration.response import assert_error_response, assert_response_header, read_response_body_string
from tests.postgres_testing import generate_async_session

# 2024-03-14 05:55:44.500


@pytest.mark.parametrize(
    "start, limit, after, expected_sub_ids",
    [
        (0, 99, None, [PUBLIC_SITE_DER_ID]),
        (0, 99, datetime(2024, 3, 14, 5, 55, 44, tzinfo=timezone.utc), [PUBLIC_SITE_DER_ID]),
        (0, 99, datetime(2024, 3, 14, 5, 55, 45, tzinfo=timezone.utc), []),
        (1, 99, None, []),
        (None, None, None, [PUBLIC_SITE_DER_ID]),
    ],
)
@pytest.mark.anyio
async def test_get_der_list(
    client: AsyncClient,
    valid_headers: dict,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_sub_ids: list[int],
):
    """Simple test of pagination"""

    # Arrange
    site_id = 1
    der_id = PUBLIC_SITE_DER_ID
    der_list_uri = uri.DERListUri.format(site_id=site_id, der_id=der_id) + build_paging_params(
        start=start, limit=limit, changed_after=after
    )

    # Act
    response = await client.get(der_list_uri, headers=valid_headers)

    # Assert
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: DERListResponse = DERListResponse.from_xml(body)
    assert parsed_response.href == uri.DERListUri.format(site_id=site_id, der_id=der_id)
    assert parsed_response.results == len(expected_sub_ids)

    if len(expected_sub_ids) > 0:
        assert len(parsed_response.DER_) == len(expected_sub_ids)
        assert all(d.href == uri.DERUri.format(site_id=site_id, der_id=der_id) for d in parsed_response.DER_)
    else:
        assert parsed_response.DER_ is None


@pytest.mark.parametrize(
    "site_id, expected_der_id",
    [
        (1, PUBLIC_SITE_DER_ID),
        (2, PUBLIC_SITE_DER_ID),
        (3, None),
        (4, PUBLIC_SITE_DER_ID),
    ],
)
@pytest.mark.anyio
async def test_get_der(
    client: AsyncClient,
    valid_headers: dict,
    site_id: int,
    expected_der_id: Optional[int],
):
    """Simple test of fetch"""

    # Arrange
    der_id = PUBLIC_SITE_DER_ID
    der_uri = uri.DERUri.format(site_id=site_id, der_id=der_id)

    # Act
    response = await client.get(der_uri, headers=valid_headers)

    # Assert
    if expected_der_id is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0

        parsed_response: DER = DER.from_xml(body)
        assert parsed_response.href == der_uri


@pytest.mark.parametrize(
    "site_id, has_entity",
    [
        (1, True),
        (2, False),
        (3, False),
        (4, False),
    ],
)
@pytest.mark.anyio
async def test_get_der_sub_entities(
    client: AsyncClient,
    valid_headers: dict,
    site_id: int,
    has_entity: bool,
):
    """Simple test of fetch on DER Availability, Capability, Setting, Status. Unit test coverage
    will ensure the specifics in greater detail"""

    der_id = PUBLIC_SITE_DER_ID

    # Availability
    availability_uri = uri.DERAvailabilityUri.format(site_id=site_id, der_id=der_id)
    response = await client.get(availability_uri, headers=valid_headers)
    if has_entity:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        availability: DERAvailability = DERAvailability.from_xml(body)
        assert availability.href == availability_uri
    else:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)

    # Capability
    capability_uri = uri.DERCapabilityUri.format(site_id=site_id, der_id=der_id)
    response = await client.get(capability_uri, headers=valid_headers)
    if has_entity:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        capability: DERCapability = DERCapability.from_xml(body)
        assert capability.href == capability_uri
    else:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)

    # Setting
    setting_uri = uri.DERSettingsUri.format(site_id=site_id, der_id=der_id)
    response = await client.get(setting_uri, headers=valid_headers)
    if has_entity:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        settings: DERSettings = DERSettings.from_xml(body)
        assert settings.href == setting_uri
    else:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)

    # Status
    status_uri = uri.DERStatusUri.format(site_id=site_id, der_id=der_id)
    response = await client.get(status_uri, headers=valid_headers)
    if has_entity:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        status: DERStatus = DERStatus.from_xml(body)
        assert status.href == status_uri
    else:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)


async def snapshot_sub_entity_count(session: AsyncSession, sub_entity_type: type) -> int:
    return (await session.execute(select(func.count()).select_from(sub_entity_type))).scalar_one()


async def assert_sub_entity_count(
    session: AsyncSession, sub_entity_type: type, before_count: int, expected_not_found: bool, expected_update: bool
):
    after_count = await snapshot_sub_entity_count(session, sub_entity_type)

    if expected_not_found:
        assert before_count == after_count
    elif expected_update:
        assert before_count == after_count
    else:
        assert (before_count + 1) == after_count


@pytest.mark.parametrize(
    "site_id, expected_not_found, expected_update",
    [
        (1, False, True),
        (2, False, False),
        (3, True, False),
        (4, False, False),
    ],
)
@pytest.mark.anyio
async def test_roundtrip_upsert_der_availability(
    pg_base_config,
    client: AsyncClient,
    valid_headers: dict,
    site_id: int,
    expected_not_found: bool,
    expected_update: bool,
):
    """Simple test of insert/update on DER Availability."""

    der_id = PUBLIC_SITE_DER_ID

    async with generate_async_session(pg_base_config) as session:
        before_count = await snapshot_sub_entity_count(session, SiteDERAvailability)

    # Availability
    availability_uri = uri.DERAvailabilityUri.format(site_id=site_id, der_id=der_id)
    availability: DERAvailability = generate_class_instance(DERAvailability, seed=2001, generate_relationships=True)
    response = await client.put(availability_uri, headers=valid_headers, content=availability.to_xml(skip_empty=True))
    if expected_not_found:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        # Now fetch the value we just sent and validate it round tripped OK
        response = await client.get(availability_uri, headers=valid_headers)
        assert_response_header(response, HTTPStatus.OK)
        actual_availability: DERAvailability = DERAvailability.from_xml(read_response_body_string(response))

        assert_class_instance_equality(
            DERAvailability,
            availability,
            actual_availability,
            ignored_properties=set(["href", "subscribable", "type", "readingTime"]),
        )
        assert_nowish(actual_availability.readingTime)  # Should be set to server time

    async with generate_async_session(pg_base_config) as session:
        await assert_sub_entity_count(session, SiteDERAvailability, before_count, expected_not_found, expected_update)


@pytest.mark.parametrize(
    "site_id, expected_not_found, expected_update",
    [
        (1, False, True),
        (2, False, False),
        (3, True, False),
        (4, False, False),
    ],
)
@pytest.mark.anyio
async def test_roundtrip_upsert_der_capability(
    pg_base_config,
    client: AsyncClient,
    valid_headers: dict,
    site_id: int,
    expected_not_found: bool,
    expected_update: bool,
):
    """Simple test of insert/update on DER Capability."""

    der_id = PUBLIC_SITE_DER_ID

    async with generate_async_session(pg_base_config) as session:
        before_count = await snapshot_sub_entity_count(session, SiteDERRating)

    # Capability
    capability_uri = uri.DERCapabilityUri.format(site_id=site_id, der_id=der_id)
    capability: DERCapability = generate_class_instance(DERCapability, seed=3001, generate_relationships=True)
    capability.modesSupported = "0"
    response = await client.put(capability_uri, headers=valid_headers, content=capability.to_xml(skip_empty=True))
    if expected_not_found:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        # Now fetch the value we just sent and validate it round tripped OK
        response = await client.get(capability_uri, headers=valid_headers)
        assert_response_header(response, HTTPStatus.OK)
        actual_capability: DERCapability = DERCapability.from_xml(read_response_body_string(response))

        assert_class_instance_equality(
            DERCapability,
            capability,
            actual_capability,
            ignored_properties=set(["href", "subscribable", "type"]),
        )

    async with generate_async_session(pg_base_config) as session:
        await assert_sub_entity_count(session, SiteDERRating, before_count, expected_not_found, expected_update)


@pytest.mark.parametrize(
    "site_id, expected_not_found, expected_update",
    [
        (1, False, True),
        (2, False, False),
        (3, True, False),
        (4, False, False),
    ],
)
@pytest.mark.anyio
async def test_roundtrip_upsert_der_setting(
    pg_base_config,
    client: AsyncClient,
    valid_headers: dict,
    site_id: int,
    expected_not_found: bool,
    expected_update: bool,
):
    """Simple test of insert/update on DER Setting."""

    der_id = PUBLIC_SITE_DER_ID

    async with generate_async_session(pg_base_config) as session:
        before_count = await snapshot_sub_entity_count(session, SiteDERSetting)

    # Setting
    setting_uri = uri.DERSettingsUri.format(site_id=site_id, der_id=der_id)
    settings: DERSettings = generate_class_instance(DERSettings, seed=4001, generate_relationships=True)
    settings.modesEnabled = "0"
    response = await client.put(setting_uri, headers=valid_headers, content=settings.to_xml(skip_empty=True))
    if expected_not_found:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        # Now fetch the value we just sent and validate it round tripped OK
        response = await client.get(setting_uri, headers=valid_headers)
        assert_response_header(response, HTTPStatus.OK)
        actual_settings: DERSettings = DERSettings.from_xml(read_response_body_string(response))

        assert_class_instance_equality(
            DERSettings,
            settings,
            actual_settings,
            ignored_properties=set(["href", "subscribable", "type", "updatedTime"]),
        )
        assert_nowish(actual_settings.updatedTime)  # Should be set to server time

    async with generate_async_session(pg_base_config) as session:
        await assert_sub_entity_count(session, SiteDERSetting, before_count, expected_not_found, expected_update)


@pytest.mark.parametrize(
    "site_id, expected_not_found, expected_update",
    [
        (1, False, True),
        (2, False, False),
        (3, True, False),
        (4, False, False),
    ],
)
@pytest.mark.anyio
async def test_roundtrip_upsert_der_status(
    pg_base_config,
    client: AsyncClient,
    valid_headers: dict,
    site_id: int,
    expected_not_found: bool,
    expected_update: bool,
):
    """Simple test of insert/update on DER Status."""

    der_id = PUBLIC_SITE_DER_ID

    async with generate_async_session(pg_base_config) as session:
        before_count = await snapshot_sub_entity_count(session, SiteDERStatus)

    # Status
    status_uri = uri.DERStatusUri.format(site_id=site_id, der_id=der_id)
    status: DERStatus = generate_class_instance(DERStatus, seed=13, generate_relationships=True)
    status.alarmStatus = "1"
    status.genConnectStatus.value = "2"
    status.storConnectStatus.value = "4"
    status.manufacturerStatus.value = "sts"
    response = await client.put(status_uri, headers=valid_headers, content=status.to_xml(skip_empty=True))
    if expected_not_found:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        # Now fetch the value we just sent and validate it round tripped OK
        response = await client.get(status_uri, headers=valid_headers)
        assert_response_header(response, HTTPStatus.OK)
        actual_status: DERStatus = DERStatus.from_xml(read_response_body_string(response))

        assert_class_instance_equality(
            DERStatus,
            status,
            actual_status,
            ignored_properties=set(["href", "subscribable", "type", "readingTime"]),
        )
        assert_nowish(actual_status.readingTime)  # Should be set to server time

    async with generate_async_session(pg_base_config) as session:
        await assert_sub_entity_count(session, SiteDERStatus, before_count, expected_not_found, expected_update)
