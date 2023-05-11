import unittest.mock as mock
from datetime import date, datetime

import pytest

from envoy.server.exception import NotFoundError
from envoy.server.manager.derp import DERControlManager, DERProgramManager
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.schema.sep2.der import DERControlListResponse, DERProgramListResponse, DERProgramResponse
from tests.data.fake.generator import generate_class_instance
from tests.unit.mocks import assert_mock_session, create_mock_session


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch_list(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_does: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    agg_id = 123
    site_id = 456
    doe_count = 789
    existing_site = generate_class_instance(Site)
    mapped_list = generate_class_instance(DERProgramListResponse)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = existing_site
    mock_count_does.return_value = doe_count
    mock_DERProgramMapper.doe_program_list_response = mock.Mock(return_value=mapped_list)

    # Act
    result = await DERProgramManager.fetch_list_for_site(mock_session, agg_id, site_id)

    # Assert
    assert result is mapped_list
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_count_does.assert_called_once_with(mock_session, agg_id, site_id, datetime.min)
    mock_DERProgramMapper.doe_program_list_response.assert_called_once_with(site_id, doe_count)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch_list_site_dne(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_does: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Checks that if the crud layer indicates site doesn't exist then the manager will raise an exception"""
    # Arrange
    agg_id = 123
    site_id = 456

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_list_for_site(mock_session, agg_id, site_id)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_count_does.assert_not_called()
    mock_DERProgramMapper.doe_program_list_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERProgramMapper")
async def test_program_fetch(
    mock_DERProgramMapper: mock.MagicMock,
    mock_count_does: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    agg_id = 123
    site_id = 456
    doe_count = 789
    existing_site = generate_class_instance(Site)
    mapped_program = generate_class_instance(DERProgramResponse)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = existing_site
    mock_count_does.return_value = doe_count
    mock_DERProgramMapper.doe_program_response = mock.Mock(return_value=mapped_program)

    # Act
    result = await DERProgramManager.fetch_doe_program_for_site(mock_session, agg_id, site_id)

    # Assert
    assert result is mapped_program
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_count_does.assert_called_once_with(mock_session, agg_id, site_id, datetime.min)
    mock_DERProgramMapper.doe_program_response.assert_called_once_with(site_id, doe_count)
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
    agg_id = 123
    site_id = 456

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_doe_program_for_site(mock_session, agg_id, site_id)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_count_does.assert_not_called()
    mock_DERProgramMapper.doe_program_response.assert_not_called()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_does")
@mock.patch("envoy.server.manager.derp.count_does")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_doe_controls_for_site(
    mock_DERControlMapper: mock.MagicMock, mock_count_does: mock.MagicMock, mock_select_does: mock.MagicMock
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    agg_id = 123
    site_id = 456
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
    result = await DERControlManager.fetch_doe_controls_for_site(
        mock_session, agg_id, site_id, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list

    mock_count_does.assert_called_once_with(mock_session, agg_id, site_id, changed_after)
    mock_select_does.assert_called_once_with(mock_session, agg_id, site_id, start, changed_after, limit)
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(does_page, doe_count, site_id)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.derp.select_does_for_day")
@mock.patch("envoy.server.manager.derp.count_does_for_day")
@mock.patch("envoy.server.manager.derp.DERControlMapper")
async def test_fetch_doe_controls_for_site_for_day(
    mock_DERControlMapper: mock.MagicMock,
    mock_count_does_for_day: mock.MagicMock,
    mock_select_does_for_day: mock.MagicMock,
):
    """Tests that the underlying dependencies pipe their outputs correctly into the downstream inputs"""
    # Arrange
    agg_id = 123
    site_id = 456
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

    mock_session = create_mock_session()
    mock_count_does_for_day.return_value = doe_count
    mock_select_does_for_day.return_value = does_page
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)

    # Act
    result = await DERControlManager.fetch_doe_controls_for_site_day(
        mock_session, agg_id, site_id, day, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list

    mock_count_does_for_day.assert_called_once_with(mock_session, agg_id, site_id, day, changed_after)
    mock_select_does_for_day.assert_called_once_with(mock_session, agg_id, site_id, day, start, changed_after, limit)
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(does_page, doe_count, site_id)
    assert_mock_session(mock_session)
