from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import pytest
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from httpx import AsyncClient
from sqlalchemy import update

from envoy.server.model.doe import SiteControlGroup
from tests.integration.request import build_paging_params
from tests.integration.response import assert_error_response, assert_response_header, read_response_body_string


@pytest.mark.parametrize(
    "site_id, fsa_id, expected_response",
    [
        (1, 1, HTTPStatus.OK),
        (1, 2, HTTPStatus.OK),
        (2, 1, HTTPStatus.OK),
        (1, 3, HTTPStatus.NOT_FOUND),  # Site isn't accessible to aggregator
        (3, 1, HTTPStatus.NOT_FOUND),
        (99, 1, HTTPStatus.NOT_FOUND),
    ],
)
@pytest.mark.anyio
async def test_get_function_set_assignments(
    site_id: int,
    fsa_id: int,
    expected_response: HTTPStatus,
    client: AsyncClient,
    valid_headers: dict,
):
    """Simple test of a valid get - validates that the response looks like XML"""

    # Arrange
    fsa_url = uri.FunctionSetAssignmentsUri.format(site_id=site_id, fsa_id=fsa_id)

    # Act
    response = await client.get(fsa_url, headers=valid_headers)

    # Assert
    assert_response_header(response, expected_response)

    if expected_response == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0

        parsed_response: FunctionSetAssignmentsResponse = FunctionSetAssignmentsResponse.from_xml(body)
        assert parsed_response.href == uri.FunctionSetAssignmentsUri.format(site_id=site_id, fsa_id=fsa_id)
        assert parsed_response.DERProgramListLink.href == uri.DERProgramFSAListUri.format(
            site_id=site_id, fsa_id=fsa_id
        ), "DERP list should use FSA scoped variant"
        assert parsed_response.TariffProfileListLink.href == uri.TariffProfileFSAListUri.format(
            site_id=site_id, fsa_id=fsa_id
        ), "Tariff list should use FSA scoped variant"
    else:
        assert_error_response(response)


@pytest.mark.parametrize(
    "start, limit, after, expected_fsa_ids",
    [
        (None, None, None, [1]),
        (0, 99, None, [1, 2]),
        (1, 99, None, [2]),
        (0, 99, datetime(2000, 1, 1, tzinfo=timezone.utc), [1, 2]),
        (0, 99, datetime(2030, 1, 1, tzinfo=timezone.utc), []),
        (0, 99, datetime(2023, 1, 2, 12, 1, 3, tzinfo=timezone.utc), [2]),
    ],
)
@pytest.mark.anyio
async def test_get_function_set_assignments_list(
    client: AsyncClient,
    valid_headers: dict,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_fsa_ids,
):
    """Simple test of a valid get/pagination - validates that the response contains the FSA IDs we expect"""

    # Arrange
    site_id = 1
    fsal_url = uri.FunctionSetAssignmentsListUri.format(site_id=site_id) + build_paging_params(start, limit, after)

    # Act
    response = await client.get(fsal_url, headers=valid_headers)

    # Assert
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: FunctionSetAssignmentsListResponse = FunctionSetAssignmentsListResponse.from_xml(body)
    # Handle None case when there are no assignments
    actual_assignments = parsed_response.FunctionSetAssignments or []
    assert len(actual_assignments) == len(expected_fsa_ids)
    assert expected_fsa_ids == [int(fsa.href.split("/")[-1]) for fsa in actual_assignments]


@pytest.mark.parametrize(
    "scg_ids_to_none, expected_fsa_ids_counts",
    [
        ([], [(1, 2, 0), (2, 0, 0), (3, 1, 0)]),
        ([1, 2, 3], [(1, 0, 0), (2, 0, 0)]),
        ([1], [(1, 1, 0), (2, 0, 0), (3, 1, 0)]),
    ],
)
@pytest.mark.anyio
async def test_get_function_set_assignments_list_with_none_fsa_id(
    pg_base_config,
    client: AsyncClient,
    valid_headers: dict,
    scg_ids_to_none: list[int],
    expected_fsa_ids_counts: list[tuple[int, int, int]],
):
    """Ensures that FSA_IDs reflect what is in the DB (and can handle None/NULL values)

    expected_fsa_ids_counts: tuple[fsa_id, expected_derp_count, expected_tp_count]"""

    # Arrange
    site_id = 1
    fsal_url = uri.FunctionSetAssignmentsListUri.format(site_id=site_id) + build_paging_params(0, 99)

    # The DB Has Tariffs with fsa_id 1,2 and SiteControlGroups with fsa_id 1
    # We want a bit more diversity so lets change SiteControlGroup #3 to have fsa_id 3
    async with generate_async_session(pg_base_config) as session:
        await session.execute(
            update(SiteControlGroup).values(fsa_id=3).where(SiteControlGroup.site_control_group_id.in_([3]))
        )
        await session.execute(
            update(SiteControlGroup)
            .values(fsa_id=None)
            .where(SiteControlGroup.site_control_group_id.in_(scg_ids_to_none))
        )
        await session.commit()

    # Act
    response = await client.get(fsal_url, headers=valid_headers)

    # Assert
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: FunctionSetAssignmentsListResponse = FunctionSetAssignmentsListResponse.from_xml(body)
    # Handle None case when there are no assignments
    actual_assignments = parsed_response.FunctionSetAssignments or []
    assert len(actual_assignments) == len(expected_fsa_ids_counts)

    for fsa, expected_id_counts in zip(actual_assignments, expected_fsa_ids_counts):
        expected_id, expected_derp_count, expected_tp_count = expected_id_counts

        assert int(fsa.href.split("/")[-1]) == expected_id, fsa.href
        assert fsa.DERProgramListLink.all_ or 0 == expected_derp_count, fsa.href
        assert fsa.TariffProfileListLink.all_ or 0 == expected_tp_count, fsa.href


@pytest.mark.anyio
async def test_get_404_Error_for_invalid_site_for_FSA_List(client: AsyncClient, valid_headers: dict):
    """Simple test of a valid get with a not existing side Id- validates that the response is a 404"""

    # Arrange
    # side_id is a random value the the Request URL can be made using the URI functions
    site_id = 12012
    fsal_url = uri.FunctionSetAssignmentsListUri.format(site_id=site_id)

    # Act
    # send the request to the URL
    response = await client.get(fsal_url, headers=valid_headers)

    # Assert
    # assert on error type and Error message
    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)


@pytest.mark.anyio
async def test_get_404_Error_for_invalid_site_in_function_set_assignment(client: AsyncClient, valid_headers: dict):
    """Test of a valid get with a not existing side Id- validates that the response is a 404"""

    # Arrange
    site_id = 12012
    fsa_id = 300
    fsal_url = uri.FunctionSetAssignmentsUri.format(site_id=site_id, fsa_id=fsa_id)

    # Act
    response = await client.get(fsal_url, headers=valid_headers)

    # Assert
    assert_response_header(response, HTTPStatus.NOT_FOUND)
