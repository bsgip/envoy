import unittest.mock as mock
from datetime import date, datetime, timezone

import pytest
from envoy_schema.server.schema.sep2.der import (
    DefaultDERControl,
    DERControlListResponse,
    DERProgramListResponse,
    DERProgramResponse,
)

from envoy.server.exception import NotFoundError
from envoy.server.manager.derp import DERControlManager, DERProgramManager
from envoy.server.mapper.csip_aus.doe import DERControlListSource
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.request_state import RequestStateParameters
from tests.assert_time import assert_nowish
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
    default_doe = generate_class_instance(DefaultDoeConfiguration)
    mapped_list = generate_class_instance(DERProgramListResponse)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = existing_site
    mock_count_does.return_value = doe_count
    mock_DERProgramMapper.doe_program_list_response = mock.Mock(return_value=mapped_list)
    rsp_params = RequestStateParameters(agg_id, "651")

    # Act
    result = await DERProgramManager.fetch_list_for_site(mock_session, rsp_params, site_id, default_doe)

    # Assert
    assert result is mapped_list
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_count_does.assert_called_once_with(mock_session, agg_id, site_id, datetime.min)
    mock_DERProgramMapper.doe_program_list_response.assert_called_once_with(rsp_params, site_id, doe_count, default_doe)
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
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = None
    rsp_params = RequestStateParameters(agg_id, None)

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_list_for_site(mock_session, rsp_params, site_id, default_doe)

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
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = existing_site
    mock_count_does.return_value = doe_count
    mock_DERProgramMapper.doe_program_response = mock.Mock(return_value=mapped_program)
    rsp_params = RequestStateParameters(agg_id, None)

    # Act
    result = await DERProgramManager.fetch_doe_program_for_site(mock_session, rsp_params, site_id, default_doe)

    # Assert
    assert result is mapped_program
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_count_does.assert_called_once_with(mock_session, agg_id, site_id, datetime.min)
    mock_DERProgramMapper.doe_program_response.assert_called_once_with(rsp_params, site_id, doe_count, default_doe)
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
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mock_session = create_mock_session()
    mock_select_single_site_with_site_id.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await DERProgramManager.fetch_doe_program_for_site(
            mock_session, RequestStateParameters(agg_id, None), site_id, default_doe
        )

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
    rsp_params = RequestStateParameters(agg_id, None)

    # Act
    result = await DERControlManager.fetch_doe_controls_for_site(
        mock_session, rsp_params, site_id, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list

    mock_count_does.assert_called_once_with(mock_session, agg_id, site_id, changed_after)
    mock_select_does.assert_called_once_with(mock_session, agg_id, site_id, start, changed_after, limit)
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        rsp_params, does_page, doe_count, site_id, DERControlListSource.DER_CONTROL_LIST
    )
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
    rsp_params = RequestStateParameters(agg_id, None)

    mock_session = create_mock_session()
    mock_count_does_for_day.return_value = doe_count
    mock_select_does_for_day.return_value = does_page
    mock_DERControlMapper.map_to_list_response = mock.Mock(return_value=mapped_list)

    # Act
    result = await DERControlManager.fetch_doe_controls_for_site_day(
        mock_session, rsp_params, site_id, day, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list

    mock_count_does_for_day.assert_called_once_with(mock_session, agg_id, site_id, day, changed_after)
    mock_select_does_for_day.assert_called_once_with(mock_session, agg_id, site_id, day, start, changed_after, limit)
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        rsp_params, does_page, doe_count, site_id, DERControlListSource.DER_CONTROL_LIST
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
    agg_id = 123
    site_id = 456
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
    rsp_params = RequestStateParameters(agg_id, "651")

    # Act
    result = await DERControlManager.fetch_active_doe_controls_for_site(
        mock_session, rsp_params, site_id, start, changed_after, limit
    )

    # Assert
    assert result is mapped_list
    mock_select_does_at_timestamp.assert_called_once()
    mock_count_does_at_timestamp.assert_called_once()
    mock_DERControlMapper.map_to_list_response.assert_called_once_with(
        rsp_params, returned_does, returned_count, site_id, DERControlListSource.ACTIVE_DER_CONTROL_LIST
    )

    # The timestamp should be (roughly) utc now and should match for both calls
    actual_now: datetime = mock_select_does_at_timestamp.call_args_list[0].args[3]
    assert actual_now == mock_count_does_at_timestamp.call_args_list[0].args[3]
    assert actual_now.tzinfo == timezone.utc
    assert_nowish(actual_now)
    mock_select_does_at_timestamp.assert_called_once_with(
        mock_session, agg_id, site_id, actual_now, start, changed_after, limit
    )
    mock_count_does_at_timestamp.assert_called_once_with(mock_session, agg_id, site_id, actual_now, changed_after)

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
    agg_id = 123
    site_id = 456
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    returned_site = generate_class_instance(Site)

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    rsp_params = RequestStateParameters(agg_id, "651")

    mock_select_single_site_with_site_id.return_value = returned_site
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    result = await DERControlManager.fetch_default_doe_controls_for_site(mock_session, rsp_params, site_id, default_doe)

    # Assert
    assert result is mapped_control
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_DERControlMapper.map_to_default_response.assert_called_once_with(default_doe)

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
    agg_id = 123
    site_id = 456
    default_doe = generate_class_instance(DefaultDoeConfiguration)

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    rsp_params = RequestStateParameters(agg_id, "651")

    mock_select_single_site_with_site_id.return_value = None
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    with pytest.raises(NotFoundError):
        await DERControlManager.fetch_default_doe_controls_for_site(mock_session, rsp_params, site_id, default_doe)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
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
    agg_id = 123
    site_id = 456
    default_doe = None

    returned_site = generate_class_instance(Site)

    mapped_control = generate_class_instance(DefaultDERControl)

    mock_session = create_mock_session()
    rsp_params = RequestStateParameters(agg_id, "651")

    mock_select_single_site_with_site_id.return_value = returned_site
    mock_DERControlMapper.map_to_default_response = mock.Mock(return_value=mapped_control)

    # Act
    with pytest.raises(NotFoundError):
        await DERControlManager.fetch_default_doe_controls_for_site(mock_session, rsp_params, site_id, default_doe)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(mock_session, site_id, agg_id)
    mock_DERControlMapper.map_to_default_response.assert_not_called()

    assert_mock_session(mock_session)
