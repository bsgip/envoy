from unittest import mock

import pytest

# from envoy.server.mapper.sep2.function_set_assignments import FunctionSetAssignmentsMapper
from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.manager.function_set_assignments import FunctionSetAssignmentsManager
from tests.data.fake import generator


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper")
async def test_function_set_assignments_fetch_function_set_assignments_for_aggregator_and_site(
    mock_FunctionSetAssignmentsMapper: mock.MagicMock,
):
    """Check the manager will handle interacting with its responses"""

    # Arrange
    mock_session: AsyncSession = mock.Mock(spec_set={})  # The session should not be interacted with directly
    site_id = 1
    aggregator_id = 321
    tariff_count = 3
    fsa_id = 1
    mapped_fsa: FunctionSetAssignmentsResponse = generator.generate_class_instance(FunctionSetAssignmentsResponse)

    # Just do a simple passthrough
    mock_FunctionSetAssignmentsMapper.map_to_response = mock.Mock(return_value=mapped_fsa)

    # Act
    with mock.patch("envoy.server.manager.function_set_assignments.pricing.select_tariff_count") as select_tariff_count:
        select_tariff_count.return_value = tariff_count
        result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_for_aggregator_and_site(
            session=mock_session, fsa_id=fsa_id, site_id=site_id, aggregator_id=aggregator_id
        )

    # Assert
    assert result is mapped_fsa
    mock_session.assert_not_called()  # Ensure the session isn't modified outside of just passing it down the call stack
    mock_FunctionSetAssignmentsMapper.map_to_response.assert_called_once_with(
        fsa_id=fsa_id, site_id=site_id, doe_count=1, tariff_count=tariff_count
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper")
async def test_function_set_assignments_fetch_function_set_assignments_list_for_aggregator_and_site(
    mock_FunctionSetAssignmentsMapper: mock.MagicMock,
):
    """Check the manager will handle interacting with its responses"""

    # Arrange
    mock_session: AsyncSession = mock.Mock(spec_set={})  # The session should not be interacted with directly
    aggregator_id = 321
    site_id = 1
    mapped_fsa: FunctionSetAssignmentsResponse = generator.generate_class_instance(FunctionSetAssignmentsResponse)
    mapped_fsal: FunctionSetAssignmentsListResponse = generator.generate_class_instance(
        FunctionSetAssignmentsListResponse
    )

    # Just do a simple passthrough
    mock_FunctionSetAssignmentsMapper.map_to_list_response = mock.Mock(return_value=mapped_fsal)

    # Act
    with mock.patch(
        (
            "envoy.server.manager.function_set_assignments."
            "FunctionSetAssignmentsManager.fetch_function_set_assignments_for_aggregator_and_site"
        )
    ) as fetch_function_set_assignments_for_aggregator_and_site:
        fetch_function_set_assignments_for_aggregator_and_site.return_value = mapped_fsa
        result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_list_for_aggregator_and_site(
            session=mock_session, aggregator_id=aggregator_id, site_id=site_id
        )

    # Assert
    assert result == mapped_fsal
    mock_session.assert_not_called()  # Ensure the session isn't modified outside of just passing it down the call stack
    mock_FunctionSetAssignmentsMapper.map_to_list_response.assert_called_once_with(
        function_set_assignments=[mapped_fsa], site_id=site_id
    )
