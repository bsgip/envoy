from http import HTTPStatus

import pytest
from httpx import AsyncClient

from envoy.server.schema import uri
from envoy.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from tests.integration.response import assert_response_header, read_response_body_string


@pytest.mark.anyio
async def test_get_function_set_assignments(client: AsyncClient, valid_headers: dict):
    """Simple test of a valid get - validates that the response looks like XML"""

    # Arrange
    site_id = 1
    fsa_id = 1
    fsa_url = uri.FunctionSetAssignmentsUri.format(site_id=site_id, fsa_id=fsa_id)

    # Act
    response = await client.get(fsa_url, headers=valid_headers)

    # Assert
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: FunctionSetAssignmentsResponse = FunctionSetAssignmentsResponse.from_xml(body)
    assert parsed_response.href == uri.FunctionSetAssignmentsUri.format(site_id=site_id, fsa_id=fsa_id)


@pytest.mark.anyio
async def test_get_function_set_assignments_list(client: AsyncClient, valid_headers: dict):
    """Simple test of a valid get - validates that the response looks like XML"""

    # Arrange
    site_id = 1
    fsal_url = uri.FunctionSetAssignmentsListUri.format(site_id=site_id)

    # Act
    response = await client.get(fsal_url, headers=valid_headers)

    # Assert
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: FunctionSetAssignmentsListResponse = FunctionSetAssignmentsListResponse.from_xml(body)
    assert parsed_response.href == fsal_url
    assert len(parsed_response.FunctionSetAssignments) == 1
    assert parsed_response.FunctionSetAssignments[0].href == uri.FunctionSetAssignmentsUri.format(
        site_id=site_id, fsa_id=1
    )
