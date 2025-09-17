from datetime import datetime, timezone
from unittest import mock

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)

from envoy.server.manager.function_set_assignments import FunctionSetAssignmentsManager
from envoy.server.model.config.server import RuntimeServerConfig
from envoy.server.model.site import Site
from envoy.server.request_scope import SiteRequestScope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper.map_to_response")
@mock.patch("envoy.server.manager.function_set_assignments.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.function_set_assignments.select_site_control_group_fsa_ids")
@mock.patch("envoy.server.manager.function_set_assignments.select_tariff_fsa_ids")
@mock.patch("envoy.server.manager.function_set_assignments.count_site_control_groups_by_fsa_id")
@pytest.mark.parametrize(
    "scg_fsa_ids, tariff_fsa_ids, fsa_id, expected_null",
    [
        ([], [], 1, True),
        ([1], [], 1, False),
        ([], [1], 1, False),
        ([1], [1], 1, False),
        ([3], [2], 1, True),
        ([5, 1, 6], [2, 5, 1, 6], 6, False),
        ([5, 1, 6], [2, 5, 1, 6], 3, True),
    ],
)
async def test_fetch_function_set_assignments_for_scope(
    mock_count_site_control_groups_by_fsa_id: mock.MagicMock,
    mock_select_tariff_fsa_ids: mock.MagicMock,
    mock_select_site_control_group_fsa_ids: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_map_to_response: mock.MagicMock,
    scg_fsa_ids: list[int],
    tariff_fsa_ids: list[int],
    fsa_id: int,
    expected_null: bool,
):
    """Check the manager will check for the existence of FSAs with the ID before returning"""

    # Arrange
    mock_session = create_mock_session()  # The session should not be interacted with directly
    mapped_fsa = generate_class_instance(FunctionSetAssignmentsResponse)
    site = generate_class_instance(Site)
    scope = generate_class_instance(SiteRequestScope)
    derp_counts_by_fsa_id = {}

    mock_select_single_site_with_site_id.return_value = site
    mock_map_to_response.return_value = mapped_fsa
    mock_select_tariff_fsa_ids.return_value = tariff_fsa_ids
    mock_select_site_control_group_fsa_ids.return_value = scg_fsa_ids
    mock_count_site_control_groups_by_fsa_id.return_value = derp_counts_by_fsa_id

    # Act
    result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_for_scope(
        session=mock_session, scope=scope, fsa_id=fsa_id
    )

    # Assert
    if expected_null:
        assert result is None
        mock_map_to_response.assert_not_called()
    else:
        assert result is mapped_fsa
        mock_map_to_response.assert_called_once_with(
            scope=scope, fsa_id=fsa_id, total_tp_links=None, total_derp_links=None
        )

    assert_mock_session(mock_session)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
    )

    # These may or may not be called - depending on whether the FSA ID is found in one or the other
    if mock_select_site_control_group_fsa_ids.call_count:
        mock_select_site_control_group_fsa_ids.assert_called_once_with(mock_session, datetime.min)
    if mock_select_tariff_fsa_ids.call_count:
        mock_select_tariff_fsa_ids.assert_called_once_with(mock_session, datetime.min)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper.map_to_response")
@mock.patch("envoy.server.manager.function_set_assignments.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.function_set_assignments.select_site_control_group_fsa_ids")
@mock.patch("envoy.server.manager.function_set_assignments.select_tariff_fsa_ids")
@mock.patch("envoy.server.manager.function_set_assignments.count_site_control_groups_by_fsa_id")
async def test_fetch_function_set_assignments_for_scope_no_site(
    mock_count_site_control_groups_by_fsa_id: mock.MagicMock,
    mock_select_tariff_fsa_ids: mock.MagicMock,
    mock_select_site_control_group_fsa_ids: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_map_to_response: mock.MagicMock,
):
    """If site isn't accessible - return None"""

    # Arrange
    mock_session = create_mock_session()  # The session should not be interacted with directly
    scope = generate_class_instance(SiteRequestScope)

    mock_select_single_site_with_site_id.return_value = None

    # Act
    result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_for_scope(
        session=mock_session, scope=scope, fsa_id=1
    )

    # Assert
    assert result is None
    mock_map_to_response.assert_not_called()
    assert_mock_session(mock_session)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
    )
    mock_select_site_control_group_fsa_ids.assert_not_called()
    mock_select_tariff_fsa_ids.assert_not_called()
    mock_count_site_control_groups_by_fsa_id.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper.map_to_list_response")
@mock.patch("envoy.server.manager.function_set_assignments.RuntimeServerConfigManager.fetch_current_config")
@mock.patch("envoy.server.manager.function_set_assignments.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.function_set_assignments.select_site_control_group_fsa_ids")
@mock.patch("envoy.server.manager.function_set_assignments.select_tariff_fsa_ids")
@mock.patch("envoy.server.manager.function_set_assignments.count_site_control_groups_by_fsa_id")
@pytest.mark.parametrize(
    "scg_fsa_ids, tariff_fsa_ids, start, limit, expected_fsa_ids, expected_count",
    [
        ([], [], 0, 10, [], 0),
        ([], [], 3, 10, [], 0),
        ([1, 2], [5, 6, 1, 2], 0, 10, [1, 2, 5, 6], 4),
        ([1, 2], [5, 6, 1, 2], 1, 2, [2, 5], 4),
        ([1, 2], [], 0, 0, [], 2),
        ([2, 1], [], 0, 99, [1, 2], 2),
        ([2, 1], [2, 1, 2, 1, 1], 0, 99, [1, 2], 2),
    ],
)
async def test_fetch_function_set_assignments_list_for_scope(
    mock_count_site_control_groups_by_fsa_id: mock.MagicMock,
    mock_select_tariff_fsa_ids: mock.MagicMock,
    mock_select_site_control_group_fsa_ids: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_fetch_current_config: mock.MagicMock,
    mock_map_to_list_response: mock.MagicMock,
    scg_fsa_ids: list[int],
    tariff_fsa_ids: list[int],
    start: int,
    limit: int,
    expected_fsa_ids: list[int],
    expected_count: int,
):
    """Check that existing FSA IDs are properly combined and paginated"""

    # Arrange
    mock_session = create_mock_session()  # The session should not be interacted with directly
    mapped_fsal = generate_class_instance(FunctionSetAssignmentsListResponse)
    site = generate_class_instance(Site)
    scope = generate_class_instance(SiteRequestScope)
    config = RuntimeServerConfig()

    derp_count_by_fsa_id = {1: 44, 5: 66}

    changed_after = datetime(2022, 11, 14, tzinfo=timezone.utc)
    mock_select_single_site_with_site_id.return_value = site
    mock_map_to_list_response.return_value = mapped_fsal
    mock_fetch_current_config.return_value = config
    mock_select_tariff_fsa_ids.return_value = tariff_fsa_ids
    mock_select_site_control_group_fsa_ids.return_value = scg_fsa_ids
    mock_count_site_control_groups_by_fsa_id.return_value = derp_count_by_fsa_id

    # Act
    result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_list_for_scope(
        session=mock_session, scope=scope, start=start, limit=limit, changed_after=changed_after
    )

    # Assert
    assert result is mapped_fsal
    assert_mock_session(mock_session)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
    )
    mock_map_to_list_response.assert_called_once_with(
        scope=scope,
        fsa_ids=expected_fsa_ids,
        total_fsa_ids=expected_count,
        pollrate_seconds=config.fsal_pollrate_seconds,
        derp_counts_by_fsa_id=derp_count_by_fsa_id,
    )
    mock_select_site_control_group_fsa_ids.assert_called_once_with(mock_session, changed_after)
    mock_select_tariff_fsa_ids.assert_called_once_with(mock_session, changed_after)
    mock_fetch_current_config.assert_called_once()
    mock_count_site_control_groups_by_fsa_id.assert_called_once_with(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.function_set_assignments.FunctionSetAssignmentsMapper.map_to_list_response")
@mock.patch("envoy.server.manager.function_set_assignments.RuntimeServerConfigManager.fetch_current_config")
@mock.patch("envoy.server.manager.function_set_assignments.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.function_set_assignments.select_site_control_group_fsa_ids")
@mock.patch("envoy.server.manager.function_set_assignments.select_tariff_fsa_ids")
async def test_fetch_function_set_assignments_list_for_scope_no_site(
    mock_select_tariff_fsa_ids: mock.MagicMock,
    mock_select_site_control_group_fsa_ids: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_fetch_current_config: mock.MagicMock,
    mock_map_to_list_response: mock.MagicMock,
):
    """Check the manager will handle when there is no site available for the scope"""

    # Arrange
    mock_session = create_mock_session()  # The session should not be interacted with directly
    scope = generate_class_instance(SiteRequestScope)

    mock_select_single_site_with_site_id.return_value = None

    # Act
    result = await FunctionSetAssignmentsManager.fetch_function_set_assignments_list_for_scope(
        session=mock_session, scope=scope, start=0, limit=99, changed_after=datetime.min
    )

    # Assert
    assert result is None
    assert_mock_session(mock_session)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
    )
    mock_map_to_list_response.assert_not_called()
    mock_select_site_control_group_fsa_ids.assert_not_called()
    mock_select_tariff_fsa_ids.assert_not_called()
    mock_fetch_current_config.assert_not_called()
