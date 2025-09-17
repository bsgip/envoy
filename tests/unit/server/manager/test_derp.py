import unittest.mock as mock
from datetime import datetime, timezone
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
from envoy.server.model.config.server import RuntimeServerConfig
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup
from envoy.server.model.site import DefaultSiteControl, Site
from envoy.server.request_scope import DeviceOrAggregatorRequestScope, SiteRequestScope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_control_groups")
@mock.patch("envoy.server.manager.derp.count_site_control_groups")
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.count_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
@mock.patch("envoy.server.manager.derp.utc_now")
@mock.patch("envoy.server.manager.derp.RuntimeServerConfigManager.fetch_current_config")
async def test_program_fetch_list_for_scope(
    mock_fetch_current_config: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_active_does_include_deleted: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
    mock_count_site_control_groups: mock.MagicMock,
    mock_select_site_control_groups: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    existing_site = generate_class_instance(Site)
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    mapped_list = generate_class_instance(DERProgramListResponse)
    scope = generate_class_instance(SiteRequestScope)
    now = datetime(2020, 1, 2, tzinfo=timezone.utc)
    start = 111
    limit = 222
    fsa_id = 333
    changed_after = datetime(2021, 3, 4)
    site_control_group_count = 554
    site_control_groups = [
        generate_class_instance(SiteControlGroup, seed=101),
        generate_class_instance(SiteControlGroup, seed=202),
    ]

    mock_utc_now.return_value = now
    mock_session = create_mock_session()
    mock_select_site_with_default_site_control.return_value = existing_site
    mock_count_site_control_groups.return_value = site_control_group_count
    mock_select_site_control_groups.return_value = site_control_groups
    mock_DERProgramMapper.doe_program_list_response = mock.Mock(return_value=mapped_list)
    mock_count_active_does_include_deleted.side_effect = (
        lambda session, site_control_group_id, site, now, changed_after: site_control_group_id + 1
    )

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    result = await DERProgramManager.fetch_list_for_scope(
        mock_session, scope, default_doe, start, changed_after, limit, fsa_id
    )

    # Assert
    assert result is mapped_list

    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_select_site_control_groups.assert_called_once_with(
        mock_session, start=start, limit=limit, changed_after=changed_after, fsa_id=fsa_id
    )

    # One call to control count for each site control group
    assert mock_count_active_does_include_deleted.call_count == len(site_control_groups)

    # The counts should be passed correctly to the mapper
    assert_mock_session(mock_session)
    mock_utc_now.assert_called_once()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.count_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch_list_scope_dne(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_active_does_include_deleted: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
):
    """Checks that if the crud layer indicates site doesn't exist then the manager will raise an exception"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    fsa_id = 11

    mock_session = create_mock_session()
    mock_select_site_with_default_site_control.return_value = None
    scope = generate_class_instance(SiteRequestScope)

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_list_for_scope(mock_session, scope, default_doe, 1, datetime.min, 2, fsa_id)

    # Assert
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_active_does_include_deleted.assert_not_called()
    mock_DERProgramMapper.doe_program_list_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_control_group_by_id")
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.count_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
@mock.patch("envoy.server.manager.derp.utc_now")
async def test_program_fetch_for_scope(
    mock_utc_now: mock.MagicMock,
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_active_does_include_deleted: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
    mock_select_site_control_group_by_id: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    doe_count = 789
    derp_id = 142124
    existing_site = generate_class_instance(Site)
    mapped_program = generate_class_instance(DERProgramResponse)
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    scope = generate_class_instance(SiteRequestScope)
    now = datetime(2011, 2, 3, tzinfo=timezone.utc)
    group = generate_class_instance(SiteControlGroup)

    mock_session = create_mock_session()
    mock_select_site_with_default_site_control.return_value = existing_site
    mock_count_active_does_include_deleted.return_value = doe_count
    mock_DERProgramMapper.doe_program_response = mock.Mock(return_value=mapped_program)
    mock_utc_now.return_value = now
    mock_select_site_control_group_by_id.return_value = group

    # Act
    result = await DERProgramManager.fetch_doe_program_for_scope(mock_session, scope, derp_id, default_doe)

    # Assert
    assert result is mapped_program

    mock_select_site_control_group_by_id.assert_called_once_with(mock_session, derp_id)
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_active_does_include_deleted.assert_called_once_with(
        mock_session, derp_id, existing_site, now, datetime.min
    )
    mock_utc_now.assert_called_once()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_control_group_by_id")
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.count_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch_site_dne(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_active_does_include_deleted: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
    mock_select_site_control_group_by_id: mock.MagicMock,
):
    """Checks that if the crud layer indicates site doesn't exist then the manager will raise an exception"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    derp_id = 76662

    mock_session = create_mock_session()
    mock_select_site_with_default_site_control.return_value = None
    scope = generate_class_instance(SiteRequestScope)

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_doe_program_for_scope(mock_session, scope, derp_id, default_doe)

    # Assert
    mock_select_site_control_group_by_id.assert_not_called()
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_active_does_include_deleted.assert_not_called()
    mock_DERProgramMapper.doe_program_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_control_group_by_id")
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.count_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch_site_control_group_dne(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_active_does_include_deleted: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
    mock_select_site_control_group_by_id: mock.MagicMock,
):
    """Checks that if the crud layer indicates site doesn't exist then the manager will raise an exception"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    derp_id = 76662

    mock_session = create_mock_session()
    mock_select_site_with_default_site_control.return_value = generate_class_instance(Site)
    mock_select_site_control_group_by_id.return_value = None
    scope = generate_class_instance(SiteRequestScope)

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_doe_program_for_scope(mock_session, scope, derp_id, default_doe)

    # Assert
    mock_select_site_control_group_by_id.assert_called_once_with(mock_session, derp_id)
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_active_does_include_deleted.assert_not_called()
    mock_DERProgramMapper.doe_program_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_doe_include_deleted")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
@mock.patch("envoy.server.manager.derp.RuntimeServerConfigManager.fetch_current_config")
@mock.patch("envoy.server.manager.derp.utc_now")
@pytest.mark.parametrize(
    "selected_doe", [generate_class_instance(DynamicOperatingEnvelope, site_control_group_id=123), None]
)
async def test_fetch_doe_control_for_scope(
    mock_utc_now: mock.MagicMock,
    mock_fetch_current_config: mock.MagicMock,
    mock_DERControlMapper: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    selected_doe: Optional[DynamicOperatingEnvelope],
):
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)
    doe_id = 15115
    derp_id = 123  # Must match the selected_doe site_control_group_id
    mock_session = create_mock_session()
    now = datetime(2022, 5, 6, 8, 9)

    mapped_doe = generate_class_instance(DERControlResponse)
    mock_select_doe_include_deleted.return_value = selected_doe
    mock_utc_now.return_value = now
    mock_DERControlMapper.map_to_response = mock.Mock(return_value=mapped_doe)

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    result = await DERControlManager.fetch_doe_control_for_scope(mock_session, scope, derp_id, doe_id)

    assert_mock_session(mock_session, committed=False)
    if selected_doe is None:
        assert result is None
    else:
        assert result is mapped_doe
        mock_DERControlMapper.map_to_response.assert_called_once_with(
            scope, derp_id, selected_doe, config.site_control_pow10_encoding, now
        )
    mock_select_doe_include_deleted.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, doe_id)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_doe_include_deleted")
async def test_fetch_doe_control_for_scope_derp_id_mismatch(mock_select_doe_include_deleted: mock.MagicMock):
    """Tests that if the DERProgram ID differs from the returned control - None is returned instead"""
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)
    doe_id = 15115
    derp_id = 199666
    mock_session = create_mock_session()
    selected_derc = generate_class_instance(DynamicOperatingEnvelope, site_control_group_id=derp_id + 1)
    mock_select_doe_include_deleted.return_value = selected_derc

    result = await DERControlManager.fetch_doe_control_for_scope(mock_session, scope, derp_id, doe_id)

    assert_mock_session(mock_session, committed=False)
    assert result is None

    mock_select_doe_include_deleted.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, doe_id)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.select_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.count_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
@mock.patch("envoy.server.manager.derp.utc_now")
@mock.patch("envoy.server.manager.derp.RuntimeServerConfigManager.fetch_current_config")
async def test_fetch_doe_controls_for_scope(
    mock_fetch_current_config: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
    mock_DERControlMapper: mock.MagicMock,
    mock_count_active_does_include_deleted: mock.MagicMock,
    mock_select_active_does_include_deleted: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    existing_site = generate_class_instance(Site)
    doe_count = 789
    start = 11
    limit = 34
    derp_id = 56156
    changed_after = datetime(2022, 11, 12, 4, 5, 6)
    does_page = [
        generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False),
        generate_class_instance(DynamicOperatingEnvelope, seed=202, optional_is_none=True),
    ]
    now = datetime(2023, 6, 7, 8, 9, 0, tzinfo=timezone.utc)
    mapped_list = generate_class_instance(DERControlListResponse)

    mock_session = create_mock_session()
    mock_count_active_does_include_deleted.return_value = doe_count
    mock_select_active_does_include_deleted.return_value = does_page
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)
    mock_utc_now.return_value = now
    mock_select_single_site_with_site_id.return_value = existing_site

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    result = await DERControlManager.fetch_doe_controls_for_scope(
        mock_session, scope, derp_id, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list

    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_active_does_include_deleted.assert_called_once_with(
        mock_session, derp_id, existing_site, now, changed_after
    )
    mock_select_active_does_include_deleted.assert_called_once_with(
        mock_session, derp_id, existing_site, now, start, changed_after, limit
    )
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        scope,
        derp_id,
        does_page,
        doe_count,
        DERControlListSource.DER_CONTROL_LIST,
        config.site_control_pow10_encoding,
        now,
    )
    mock_utc_now.assert_called_once()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.select_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.count_active_does_include_deleted")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
@mock.patch("envoy.server.manager.derp.utc_now")
@mock.patch("envoy.server.manager.derp.RuntimeServerConfigManager.fetch_current_config")
async def test_fetch_doe_controls_for_scope_site_dne(
    mock_fetch_current_config: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
    mock_DERControlMapper: mock.MagicMock,
    mock_count_active_does_include_deleted: mock.MagicMock,
    mock_select_active_does_include_deleted: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that if the site isn't accessible that the resulting list is empty"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    start = 11
    limit = 34
    derp_id = 51512
    changed_after = datetime(2022, 11, 12, 4, 5, 6)
    now = datetime(2023, 6, 7, 8, 9, 0, tzinfo=timezone.utc)
    mapped_list = generate_class_instance(DERControlListResponse)

    mock_session = create_mock_session()
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)
    mock_utc_now.return_value = now
    mock_select_single_site_with_site_id.return_value = None

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    result = await DERControlManager.fetch_doe_controls_for_scope(
        mock_session, scope, derp_id, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list

    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_count_active_does_include_deleted.assert_not_called()
    mock_select_active_does_include_deleted.assert_not_called()
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        scope, derp_id, [], 0, DERControlListSource.DER_CONTROL_LIST, config.site_control_pow10_encoding, now
    )
    mock_utc_now.assert_called_once()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_does_at_timestamp")
@mock.patch("envoy.server.manager.derp.count_does_at_timestamp")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
@mock.patch("envoy.server.manager.derp.RuntimeServerConfigManager.fetch_current_config")
async def test_fetch_active_doe_controls_for_site(
    mock_fetch_current_config: mock.MagicMock,
    mock_DERControlMapper: mock.MagicMock,
    mock_count_does_at_timestamp: mock.MagicMock,
    mock_select_does_at_timestamp: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    start = 789
    changed_after = datetime(2021, 2, 3, 4, 5, 6)
    limit = 101112
    derp_id = 111558

    returned_count = 11
    returned_does = [generate_class_instance(DynamicOperatingEnvelope)]

    mapped_list = generate_class_instance(DERControlListResponse)

    mock_session = create_mock_session()
    mock_select_does_at_timestamp.return_value = returned_does
    mock_count_does_at_timestamp.return_value = returned_count
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    result = await DERControlManager.fetch_active_doe_controls_for_scope(
        mock_session, scope, derp_id, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list
    mock_select_does_at_timestamp.assert_called_once()
    mock_count_does_at_timestamp.assert_called_once()

    # The timestamp should be (roughly) utc now and should match for both calls
    actual_now: datetime = mock_select_does_at_timestamp.call_args_list[0].args[4]
    assert actual_now == mock_count_does_at_timestamp.call_args_list[0].args[4]
    assert actual_now.tzinfo == timezone.utc
    assert_nowish(actual_now)
    mock_select_does_at_timestamp.assert_called_once_with(
        mock_session, derp_id, scope.aggregator_id, scope.site_id, actual_now, start, changed_after, limit
    )
    mock_count_does_at_timestamp.assert_called_once_with(
        mock_session, derp_id, scope.aggregator_id, scope.site_id, actual_now, changed_after
    )

    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        scope,
        derp_id,
        returned_does,
        returned_count,
        DERControlListSource.ACTIVE_DER_CONTROL_LIST,
        config.site_control_pow10_encoding,
        actual_now,
    )

    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
@mock.patch("envoy.server.manager.derp.DERControlManager._resolve_default_site_control")
@mock.patch("envoy.server.manager.derp.RuntimeServerConfigManager.fetch_current_config")
async def test_fetch_default_doe_controls_for_site(
    mock_fetch_current_config: mock.MagicMock,
    mock_resolve_default_site_control: mock.MagicMock,
    mock_DERControlMapper: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    derp_id = 771263

    returned_site = generate_class_instance(Site, generate_relationships=True)
    mock_resolve_default_site_control.return_value = returned_site.default_site_control
    mock_select_site_with_default_site_control.return_value = returned_site

    mapped_control = generate_class_instance(DefaultDERControl)
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    mock_session = create_mock_session()
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    result = await DERControlManager.fetch_default_doe_controls_for_site(mock_session, scope, derp_id, default_doe)

    # Assert
    assert result is mapped_control
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_DERControlMapper.map_to_default_response.assert_called_once_with(
        scope, returned_site.default_site_control, scope.display_site_id, derp_id, config.site_control_pow10_encoding
    )

    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_default_doe_controls_for_site_bad_site(
    mock_DERControlMapper: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    derp_id = 771263

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    mock_select_site_with_default_site_control.return_value = None
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    with pytest.raises(NotFoundError):
        await DERControlManager.fetch_default_doe_controls_for_site(mock_session, scope, derp_id, default_doe)

    # Assert
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_DERControlMapper.map_to_default_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_default_doe_controls_for_site_no_default(
    mock_DERControlMapper: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    default_doe = None
    derp_id = 88123

    returned_site = generate_class_instance(Site, generate_relationships=False)

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    mock_select_site_with_default_site_control.return_value = returned_site
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    with pytest.raises(NotFoundError):
        await DERControlManager.fetch_default_doe_controls_for_site(mock_session, scope, derp_id, default_doe)

    # Assert
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_DERControlMapper.map_to_default_response.assert_not_called()

    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_site_with_default_site_control")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
@mock.patch("envoy.server.manager.derp.RuntimeServerConfigManager.fetch_current_config")
async def test_fetch_default_doe_controls_for_site_no_global_default(
    mock_fetch_current_config: mock.MagicMock,
    mock_DERControlMapper: mock.MagicMock,
    mock_select_site_with_default_site_control: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    default_doe = None
    derp_id = 88144

    returned_site = generate_class_instance(Site, generate_relationships=True)

    mapped_control = None

    mock_session = create_mock_session()
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope)

    mock_select_site_with_default_site_control.return_value = returned_site
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    mock_fetch_current_config.return_value = RuntimeServerConfig()

    # Act
    await DERControlManager.fetch_default_doe_controls_for_site(mock_session, scope, derp_id, default_doe)

    # Assert
    mock_select_site_with_default_site_control.assert_called_once_with(mock_session, scope.site_id, scope.aggregator_id)
    mock_DERControlMapper.map_to_default_response.assert_called_once()

    assert_mock_session(mock_session)


@pytest.mark.parametrize(
    "default_doe_config, default_site_control, expected",
    [
        # misc
        (None, None, None),
        (
            DefaultDoeConfiguration(100, 200, 300, 400, 50),
            DefaultSiteControl(import_limit_active_watts=0, load_limit_active_watts=0),
            (0, 200, 300, 0, 50),
        ),
        (
            DefaultDoeConfiguration(None, 200, 300, None, 50),
            DefaultSiteControl(import_limit_active_watts=0, load_limit_active_watts=0),
            (0, 200, 300, 0, 50),
        ),
        (
            DefaultDoeConfiguration(None, None, None, None, None),
            DefaultSiteControl(import_limit_active_watts=0, load_limit_active_watts=0),
            (0, None, None, 0, None),
        ),
        # No site control
        (
            DefaultDoeConfiguration(100, 200, 300, 400, 50),
            None,
            (100, 200, 300, 400, 50),
        ),
        # Partial site control
        (
            DefaultDoeConfiguration(
                import_limit_active_watts=100,
                export_limit_active_watts=200,
                generation_limit_active_watts=300,
                load_limit_active_watts=400,
                ramp_rate_percent_per_second=50,
            ),
            DefaultSiteControl(import_limit_active_watts=111, load_limit_active_watts=444),
            (111, 200, 300, 444, 50),
        ),
        # Full site control
        (
            DefaultDoeConfiguration(
                import_limit_active_watts=100,
                export_limit_active_watts=200,
                generation_limit_active_watts=300,
                load_limit_active_watts=400,
                ramp_rate_percent_per_second=50,
            ),
            DefaultSiteControl(
                import_limit_active_watts=1,
                export_limit_active_watts=2,
                generation_limit_active_watts=3,
                load_limit_active_watts=4,
                ramp_rate_percent_per_second=5,
            ),
            (1, 2, 3, 4, 5),
        ),
        (
            None,
            DefaultSiteControl(
                import_limit_active_watts=1,
                export_limit_active_watts=2,
                generation_limit_active_watts=3,
                load_limit_active_watts=4,
                ramp_rate_percent_per_second=5,
            ),
            (1, 2, 3, 4, 5),
        ),
    ],
)
def test_resolve_default_site_control(default_doe_config, default_site_control, expected):
    """Tests all combos of resolution"""
    result = DERControlManager._resolve_default_site_control(default_doe_config, default_site_control)

    if expected is None:
        assert result is None
    else:
        assert result.import_limit_active_watts == expected[0]
        assert result.export_limit_active_watts == expected[1]
        assert result.generation_limit_active_watts == expected[2]
        assert result.load_limit_active_watts == expected[3]
        assert result.ramp_rate_percent_per_second == expected[4]
