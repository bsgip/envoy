from http import HTTPStatus

import pytest
from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from httpx import AsyncClient

from tests.integration.response import assert_error_response, assert_response_header, read_response_body_string


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
