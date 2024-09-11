from unittest import mock

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session

# from envoy.server.mapper.sep2.function_set_assignments import FunctionSetAssignmentsMapper
from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)

from envoy.server.manager.function_set_assignments import FunctionSetAssignmentsManager
from envoy.server.request_scope import SiteRequestScope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper")
async def test_function_set_assignments_fetch_function_set_assignments_for_aggregator_and_site(
    mock_FunctionSetAssignmentsMapper: mock.MagicMock,
):
    """Check the manager will handle interacting with its responses"""

    # Arrange
    mock_session = create_mock_session()  # The session should not be interacted with directly
    tariff_count = 3
    fsa_id = 1
    mapped_fsa: FunctionSetAssignmentsResponse = generate_class_instance(FunctionSetAssignmentsResponse)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    # Just do a simple passthrough
    mock_FunctionSetAssignmentsMapper.map_to_response = mock.Mock(return_value=mapped_fsa)

    # Act
    with mock.patch("envoy.server.manager.function_set_assignments.pricing.select_tariff_count") as select_tariff_count:
        select_tariff_count.return_value = tariff_count
        result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_for_scope(
            session=mock_session,
            fsa_id=fsa_id,
            scope=scope,
        )

    # Assert
    assert result is mapped_fsa
    assert_mock_session(mock_session)
    mock_FunctionSetAssignmentsMapper.map_to_response.assert_called_once_with(
        scope=scope, fsa_id=fsa_id, doe_count=1, tariff_count=tariff_count
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper")
async def test_function_set_assignments_fetch_function_set_assignments_list_for_aggregator_and_site(
    mock_FunctionSetAssignmentsMapper: mock.MagicMock,
):
    """Check the manager will handle interacting with its responses"""

    # Arrange
    mock_session = create_mock_session()  # The session should not be interacted with directly
    mapped_fsa: FunctionSetAssignmentsResponse = generate_class_instance(FunctionSetAssignmentsResponse)
    mapped_fsal: FunctionSetAssignmentsListResponse = generate_class_instance(FunctionSetAssignmentsListResponse)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    # Just do a simple passthrough
    mock_FunctionSetAssignmentsMapper.map_to_list_response = mock.Mock(return_value=mapped_fsal)

    # Act
    with mock.patch(
        (
            "envoy.server.manager.function_set_assignments."
            "FunctionSetAssignmentsManager.fetch_function_set_assignments_for_scope"
        )
    ) as fetch_function_set_assignments_for_aggregator_and_site:
        fetch_function_set_assignments_for_aggregator_and_site.return_value = mapped_fsa
        result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_list_for_scope(
            session=mock_session, scope=scope
        )

    # Assert
    assert result == mapped_fsal
    assert_mock_session(mock_session)
    mock_FunctionSetAssignmentsMapper.map_to_list_response.assert_called_once_with(
        scope=scope, function_set_assignments=[mapped_fsa]
    )
