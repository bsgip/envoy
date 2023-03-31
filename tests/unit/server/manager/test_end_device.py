import unittest.mock as mock
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.manager.end_device import EndDeviceManager
from envoy.server.model.site import Site
from envoy.server.schema.sep2.end_device import EndDeviceRequest, EndDeviceResponse
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


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.upsert_site_for_aggregator")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
@mock.patch("envoy.server.manager.end_device.datetime")
async def test_add_or_update_enddevice_for_aggregator(mock_datetime: mock.MagicMock,
                                                      mock_EndDeviceMapper: mock.MagicMock,
                                                      mock_upsert_site_for_aggregator: mock.MagicMock):
    """Checks that the enddevice update just passes through to the relevant CRUD"""
    # Arrange
    mock_session: AsyncSession = mock.Mock(spec_set={})  # The session should not be interacted with directly
    aggregator_id = 3
    end_device: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    mapped_site: Site = generate_class_instance(Site)
    now: datetime = datetime(2020, 1, 2, 3, 4)

    mock_EndDeviceMapper.map_from_request = mock.Mock(return_value=mapped_site)
    mock_upsert_site_for_aggregator.return_value
    mock_datetime.now = mock.Mock(return_value=now)

    # Act
    await EndDeviceManager.add_or_update_enddevice_for_aggregator(mock_session, aggregator_id, end_device)

    # Assert
    mock_session.assert_not_called()  # Ensure the session isn't modified outside of just passing it down the call stack
    mock_EndDeviceMapper.map_from_request.assert_called_once_with(end_device, aggregator_id, now)
    mock_upsert_site_for_aggregator.assert_called_once_with(mock_session, mapped_site)
    mock_datetime.now.assert_called_once()


# class EndDeviceListManager:
#     @staticmethod
#     async def fetch_enddevicelist_with_aggregator_id(
#         session: AsyncSession,
#         aggregator_id: int,
#         start: int,
#         after: int,
#         limit: int,
#     ) -> EndDeviceListResponse:
#         site_list = await select_all_sites_with_aggregator_id(
#             session, aggregator_id, start, datetime.fromtimestamp(after), limit
#         )
#         site_count = await select_aggregator_site_count(session, aggregator_id)
#         return EndDeviceListMapper.map_to_response(site_list, site_count)

@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.upsert_site_for_aggregator")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
@mock.patch("envoy.server.manager.end_device.datetime")
async def test_fetch_enddevicelist_with_aggregator_id(mock_datetime: mock.MagicMock,
                                                      mock_EndDeviceMapper: mock.MagicMock,
                                                      mock_upsert_site_for_aggregator: mock.MagicMock):
    """Checks that the enddevice update just passes through to the relevant CRUD"""
    # Arrange
    mock_session: AsyncSession = mock.Mock(spec_set={})  # The session should not be interacted with directly
    aggregator_id = 3
    start = 4
    after = 1678542014
    end_device: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    mapped_site: Site = generate_class_instance(Site)
    now: datetime = datetime(2020, 1, 2, 3, 4)

    mock_EndDeviceMapper.map_from_request = mock.Mock(return_value=mapped_site)
    mock_upsert_site_for_aggregator.return_value
    mock_datetime.now = mock.Mock(return_value=now)

    raise Exception("TODO")

    # Act
    await EndDeviceManager.add_or_update_enddevice_for_aggregator(mock_session, aggregator_id, end_device)

    # Assert
    mock_session.assert_not_called()  # Ensure the session isn't modified outside of just passing it down the call stack
    mock_EndDeviceMapper.map_from_request.assert_called_once_with(end_device, aggregator_id, now)
    mock_upsert_site_for_aggregator.assert_called_once_with(mock_session, mapped_site)
    mock_datetime.now.assert_called_once()