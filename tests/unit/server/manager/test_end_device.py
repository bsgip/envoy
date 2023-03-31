import unittest.mock as mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.manager.end_device import EndDeviceManager
from envoy.server.model.site import Site
from envoy.server.schema.sep2.end_device import EndDeviceResponse
from tests.data.fake.generator import generate_class_instance


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
async def test_end_device_manager_fetch_existing_device(mock_EndDeviceMapper: mock.MagicMock,
                                                         mock_select_single_site_with_site_id: mock.MagicMock):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session: AsyncSession = mock.Mock(spec_set={})  # The session should not be interacted with directly
    site_id = 1
    aggregator_id = 2
    raw_site: Site = generate_class_instance(Site)
    mapped_ed: EndDeviceResponse = generate_class_instance(EndDeviceResponse)

    # Just do a simple passthrough
    mock_select_single_site_with_site_id.return_value = raw_site
    mock_EndDeviceMapper.map_to_response = mock.Mock(return_value=mapped_ed)

    # Act
    result = await EndDeviceManager.fetch_enddevice_with_site_id(mock_session, site_id, aggregator_id)

    # Assert
    assert result is mapped_ed
    mock_session.assert_not_called()  # Ensure the session isn't modified outside of just passing it down the call stack
    mock_select_single_site_with_site_id.assert_called_once_with(session=mock_session,
                                                                 site_id=site_id,
                                                                 aggregator_id=aggregator_id)
    mock_EndDeviceMapper.map_to_response.assert_called_once_with(raw_site)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
async def test_end_device_manager_fetch_missing_device(mock_EndDeviceMapper: mock.MagicMock,
                                                       mock_select_single_site_with_site_id: mock.MagicMock):
    """Check that the manager will handle interacting with the DB and its responses when the requested site DNE"""

    # Arrange
    mock_session: AsyncSession = mock.Mock(spec_set={})  # The session should not be interacted with directly
    site_id = 1
    aggregator_id = 2

    mock_select_single_site_with_site_id.return_value = None  # database entity is missing / bad ID lookup
    mock_EndDeviceMapper.map_to_response = mock.Mock()

    # Act
    result = await EndDeviceManager.fetch_enddevice_with_site_id(mock_session, site_id, aggregator_id)

    # Assert
    assert result is None
    mock_session.assert_not_called()  # Ensure the session isn't modified outside of just passing it down the call stack
    mock_select_single_site_with_site_id.assert_called_once_with(session=mock_session,
                                                                 site_id=site_id,
                                                                 aggregator_id=aggregator_id)
    mock_EndDeviceMapper.map_to_response.assert_not_called()  # Don't map if there's nothing in the DB
