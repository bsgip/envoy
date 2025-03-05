import unittest.mock as mock
from datetime import date, datetime, timezone
from typing import Optional

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.der import (
    DefaultDERControl,
    DERControlListResponse,
    DERControlResponse,
    DERProgramListResponse,
    DERProgramResponse,
)

from envoy.server.exception import NotFoundError
from envoy.server.manager.derp import DERControlManager, DERProgramManager
from envoy.server.mapper.csip_aus.doe import DERControlListSource
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.request_scope import DeviceOrAggregatorRequestScope, SiteRequestScope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(DeviceOrAggregatorRequestScope, site_id=123),
        generate_class_instance(DeviceOrAggregatorRequestScope, site_id=None),
    ],
)
async def test_program_fetch_list_for_scope(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_does: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    scope: DeviceOrAggregatorRequestScope,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    doe_count = 789
    existing_site = generate_class_instance(Site)
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    mapped_list = generate_class_instance(DERProgramListResponse)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = existing_site
    mock_count_does.return_value = doe_count
    mock_DERProgramMapper.doe_program_list_response = mock.Mock(return_value=mapped_list)

    # Act
    result = await DERProgramManager.fetch_list_for_scope(mock_session, scope, default_doe)

    # Assert
    assert result is mapped_list

    # We only validate site existence if we are scoped to that site specifically
    if scope.site_id is None:
        mock_select_single_site_with_site_id.assert_not_called()
    else:
        mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_does.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, datetime.min)
    mock_DERProgramMapper.doe_program_list_response.assert_called_once_with(scope, doe_count, default_doe)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch_list_scope_dne(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_does: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Checks that if the crud layer indicates site doesn't exist then the manager will raise an exception"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = None
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_list_for_scope(mock_session, scope, default_doe)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_does.assert_not_called()
    mock_DERProgramMapper.doe_program_list_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(DeviceOrAggregatorRequestScope, site_id=123),
        generate_class_instance(DeviceOrAggregatorRequestScope, site_id=None),
    ],
)
async def test_program_fetch_for_scope(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_does: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    scope: DeviceOrAggregatorRequestScope,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    doe_count = 789
    existing_site = generate_class_instance(Site)
    mapped_program = generate_class_instance(DERProgramResponse)
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = existing_site
    mock_count_does.return_value = doe_count
    mock_DERProgramMapper.doe_program_response = mock.Mock(return_value=mapped_program)

    # Act
    result = await DERProgramManager.fetch_doe_program_for_scope(mock_session, scope, default_doe)

    # Assert
    assert result is mapped_program
    if scope.site_id is None:
        mock_select_single_site_with_site_id.assert_not_called()
    else:
        mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_does.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, datetime.min)
    mock_DERProgramMapper.doe_program_response.assert_called_once_with(scope, doe_count, default_doe)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch_site_dne(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_does: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Checks that if the crud layer indicates site doesn't exist then the manager will raise an exception"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = None
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_doe_program_for_scope(mock_session, scope, default_doe)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_does.assert_not_called()
    mock_DERProgramMapper.doe_program_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_doe_for_scope")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
@pytest.mark.parametrize("selected_doe", [generate_class_instance(DynamicOperatingEnvelope), None])
async def test_fetch_doe_control_for_scope(
    mock_DERControlMapper: mock.MagicMock,
    mock_select_doe_for_scope: mock.MagicMock,
    selected_doe: Optional[DynamicOperatingEnvelope],
):
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)
    doe_id = 15115
    mock_session = create_mock_session()

    mapped_doe = generate_class_instance(DERControlResponse)
    mock_select_doe_for_scope.return_value = selected_doe
    mock_DERControlMapper.map_to_response = mock.Mock(return_value=mapped_doe)

    result = await DERControlManager.fetch_doe_control_for_scope(mock_session, scope, doe_id)

    assert_mock_session(mock_session, committed=False)
    if selected_doe is None:
        assert result is None
    else:
        assert result is mapped_doe
        mock_DERControlMapper.map_to_response.assert_called_once_with(scope, selected_doe)
    mock_select_doe_for_scope.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, doe_id)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_does")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_doe_controls_for_scope(
    mock_DERControlMapper: mock.MagicMock, mock_count_does: mock.MagicMock, mock_select_does: mock.MagicMock
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)
    doe_count = 789
    start = 11
    limit = 34
    changed_after = datetime(2022, 11, 12, 4, 5, 6)
    does_page = [
        generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False),
        generate_class_instance(DynamicOperatingEnvelope, seed=202, optional_is_none=True),
    ]
    mapped_list = generate_class_instance(DERControlListResponse)

    mock_session = create_mock_session()
    mock_count_does.return_value = doe_count
    mock_select_does.return_value = does_page
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)

    # Act
    result = await DERControlManager.fetch_doe_controls_for_scope(mock_session, scope, start, changed_after, limit)

    # Assert
    assert result is mapped_list

    mock_count_does.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, changed_after)
    mock_select_does.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, start, changed_after, limit
    )
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        scope, does_page, doe_count, DERControlListSource.DER_CONTROL_LIST
    )
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_does_for_day")
@mock.patch("envoy.server.manager.derp.count_does_for_day")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_doe_controls_for_scope_for_day(
    mock_DERControlMapper: mock.MagicMock,
    mock_count_does_for_day: mock.MagicMock,
    mock_select_does_for_day: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    doe_count = 789
    start = 11
    limit = 34
    changed_after = datetime(2022, 11, 12, 4, 5, 7)
    day = date(2023, 4, 28)
    does_page = [
        generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False),
        generate_class_instance(DynamicOperatingEnvelope, seed=202, optional_is_none=True),
    ]
    mapped_list = generate_class_instance(DERControlListResponse)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    mock_session = create_mock_session()
    mock_count_does_for_day.return_value = doe_count
    mock_select_does_for_day.return_value = does_page
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)

    # Act
    result = await DERControlManager.fetch_doe_controls_for_scope_day(
        mock_session, scope, day, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list

    mock_count_does_for_day.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, day, changed_after
    )
    mock_select_does_for_day.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, day, start, changed_after, limit
    )
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        scope, does_page, doe_count, DERControlListSource.DER_CONTROL_LIST
    )
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_does_at_timestamp")
@mock.patch("envoy.server.manager.derp.count_does_at_timestamp")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_active_doe_controls_for_site(
    mock_DERControlMapper: mock.MagicMock,
    mock_count_does_at_timestamp: mock.MagicMock,
    mock_select_does_at_timestamp: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    start = 789
    changed_after = datetime(2021, 2, 3, 4, 5, 6)
    limit = 101112

    returned_count = 11
    returned_does = [generate_class_instance(DynamicOperatingEnvelope)]

    mapped_list = generate_class_instance(DERControlListResponse)

    mock_session = create_mock_session()
    mock_select_does_at_timestamp.return_value = returned_does
    mock_count_does_at_timestamp.return_value = returned_count
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)

    # Act
    result = await DERControlManager.fetch_active_doe_controls_for_scope(
        mock_session, scope, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list
    mock_select_does_at_timestamp.assert_called_once()
    mock_count_does_at_timestamp.assert_called_once()
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        scope, returned_does, returned_count, DERControlListSource.ACTIVE_DER_CONTROL_LIST
    )

    # The timestamp should be (roughly) utc now and should match for both calls
    actual_now: datetime = mock_select_does_at_timestamp.call_args_list[0].args[3]
    assert actual_now == mock_count_does_at_timestamp.call_args_list[0].args[3]
    assert actual_now.tzinfo == timezone.utc
    assert_nowish(actual_now)
    mock_select_does_at_timestamp.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, actual_now, start, changed_after, limit
    )
    mock_count_does_at_timestamp.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, actual_now, changed_after
    )

    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_default_doe_controls_for_site(
    mock_DERControlMapper: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    returned_site = generate_class_instance(Site)

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    mock_select_single_site_with_site_id.return_value = returned_site
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    result = await DERControlManager.fetch_default_doe_controls_for_site(mock_session, scope, default_doe)

    # Assert
    assert result is mapped_control
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_DERControlMapper.map_to_default_response.assert_called_once_with(scope, default_doe)

    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_default_doe_controls_for_site_bad_site(
    mock_DERControlMapper: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    mock_select_single_site_with_site_id.return_value = None
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    with pytest.raises(NotFoundError):
        await DERControlManager.fetch_default_doe_controls_for_site(mock_session, scope, default_doe)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_DERControlMapper.map_to_default_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_default_doe_controls_for_site_no_default(
    mock_DERControlMapper: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    default_doe = None

    returned_site = generate_class_instance(Site)

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    mock_select_single_site_with_site_id.return_value = returned_site
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    with pytest.raises(NotFoundError):
        await DERControlManager.fetch_default_doe_controls_for_site(mock_session, scope, default_doe)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_DERControlMapper.map_to_default_response.assert_not_called()

    assert_mock_session(mock_session)
