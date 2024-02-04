import unittest.mock as mock
from datetime import datetime

import pytest
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.api.request import RequestStateParameters
from envoy.server.exception import UnableToGenerateIdError
from envoy.server.manager.end_device import EndDeviceListManager, EndDeviceManager
from envoy.server.model.site import Site
from tests.data.fake.generator import generate_class_instance
from tests.unit.mocks import assert_mock_session, create_mock_session


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_sfdi")
async def test_end_device_manager_generate_unique_device_id_bounded_attempts(
    mock_select_single_site_with_sfdi: mock.MagicMock,
):
    """Check that the manager will abort after a fixed number of attempts to find a valid sfdi"""

    # Arrange
    mock_session: AsyncSession = create_mock_session()
    aggregator_id = 2

    # Always finds a match - so it will always continue requesting
    mock_select_single_site_with_sfdi.return_value = generate_class_instance(Site)

    # Act
    with pytest.raises(UnableToGenerateIdError):
        await EndDeviceManager.generate_unique_device_id(mock_session, aggregator_id)

    # Assert
    assert mock_select_single_site_with_sfdi.call_count > 1, "The failure should've been retried at least once"
    all_sfdis = [c.kwargs["sfdi"] for c in mock_select_single_site_with_sfdi.call_args_list]
    assert len(set(all_sfdis)) == len(all_sfdis), f"Every sfdi should be unique {all_sfdis}"
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_sfdi")
async def test_end_device_manager_generate_unique_device_id(
    mock_select_single_site_with_sfdi: mock.MagicMock,
):
    """Check that the manager will return the first unique sfdi"""

    # Arrange
    mock_session: AsyncSession = create_mock_session()
    aggregator_id = 2

    # First finds a db match and then doesn't on the second attempt
    mock_select_single_site_with_sfdi.side_effect = [generate_class_instance(Site), None]

    # Act
    (sfdi, lfdi) = await EndDeviceManager.generate_unique_device_id(mock_session, aggregator_id)

    # Assert
    assert isinstance(sfdi, int)
    assert isinstance(lfdi, str)
    assert sfdi != 0
    assert lfdi.strip() != ""
    assert mock_select_single_site_with_sfdi.call_count == 2, "There should have been a single retry"
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
async def test_end_device_manager_fetch_existing_device(
    mock_EndDeviceMapper: mock.MagicMock, mock_select_single_site_with_site_id: mock.MagicMock
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    site_id = 1
    aggregator_id = 2
    raw_site: Site = generate_class_instance(Site)
    mapped_ed: EndDeviceResponse = generate_class_instance(EndDeviceResponse)
    rsp_params = RequestStateParameters(aggregator_id, None)

    # Just do a simple passthrough
    mock_select_single_site_with_site_id.return_value = raw_site
    mock_EndDeviceMapper.map_to_response = mock.Mock(return_value=mapped_ed)

    # Act
    result = await EndDeviceManager.fetch_enddevice_with_site_id(mock_session, site_id, rsp_params)

    # Assert
    assert result is mapped_ed
    assert_mock_session(mock_session, committed=False)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=site_id, aggregator_id=aggregator_id
    )
    mock_EndDeviceMapper.map_to_response.assert_called_once_with(rsp_params, raw_site)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
async def test_end_device_manager_fetch_missing_device(
    mock_EndDeviceMapper: mock.MagicMock, mock_select_single_site_with_site_id: mock.MagicMock
):
    """Check that the manager will handle interacting with the DB and its responses when the requested site
    does not exist"""

    # Arrange
    mock_session = create_mock_session()
    site_id = 1
    aggregator_id = 2
    rsp_params = RequestStateParameters(aggregator_id, None)

    mock_select_single_site_with_site_id.return_value = None  # database entity is missing / bad ID lookup
    mock_EndDeviceMapper.map_to_response = mock.Mock()

    # Act
    result = await EndDeviceManager.fetch_enddevice_with_site_id(mock_session, site_id, rsp_params)

    # Assert
    assert result is None
    assert_mock_session(mock_session, committed=False)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=site_id, aggregator_id=aggregator_id
    )
    mock_EndDeviceMapper.map_to_response.assert_not_called()  # Don't map if there's nothing in the DB


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.upsert_site_for_aggregator")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
@mock.patch("envoy.server.manager.end_device.datetime")
@mock.patch("envoy.server.manager.end_device.select_single_site_with_sfdi")
async def test_add_or_update_enddevice_for_aggregator_with_sfdi(
    mock_select_single_site_with_sfdi: mock.MagicMock,
    mock_datetime: mock.MagicMock,
    mock_EndDeviceMapper: mock.MagicMock,
    mock_upsert_site_for_aggregator: mock.MagicMock,
):
    """Checks that the enddevice update just passes through to the relevant CRUD (assuming the sfdi is specified)"""
    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 3
    end_device: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    mapped_site: Site = generate_class_instance(Site)
    now: datetime = datetime(2020, 1, 2, 3, 4)
    rsp_params = RequestStateParameters(aggregator_id, None)

    mock_EndDeviceMapper.map_from_request = mock.Mock(return_value=mapped_site)
    mock_upsert_site_for_aggregator.return_value = 4321
    mock_datetime.now = mock.Mock(return_value=now)

    # Act
    returned_site_id = await EndDeviceManager.add_or_update_enddevice_for_aggregator(
        mock_session, rsp_params, end_device
    )
    assert returned_site_id == mock_upsert_site_for_aggregator.return_value

    # Assert
    assert_mock_session(mock_session, committed=True)
    mock_EndDeviceMapper.map_from_request.assert_called_once_with(end_device, aggregator_id, now)
    mock_upsert_site_for_aggregator.assert_called_once_with(mock_session, aggregator_id, mapped_site)
    mock_datetime.now.assert_called_once()
    mock_select_single_site_with_sfdi.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.upsert_site_for_aggregator")
@mock.patch("envoy.server.manager.end_device.EndDeviceMapper")
@mock.patch("envoy.server.manager.end_device.datetime")
@mock.patch("envoy.server.manager.end_device.select_single_site_with_sfdi")
async def test_add_or_update_enddevice_for_aggregator_no_sfdi(
    mock_select_single_site_with_sfdi: mock.MagicMock,
    mock_datetime: mock.MagicMock,
    mock_EndDeviceMapper: mock.MagicMock,
    mock_upsert_site_for_aggregator: mock.MagicMock,
):
    """Checks that the enddevice update just passes through to the relevant CRUD (assuming the sfdi is undefined)"""
    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 3
    end_device: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    end_device.sFDI = 0  # set the sfdi to 0 to trigger a regenerate
    end_device.lFDI = ""
    mapped_site: Site = generate_class_instance(Site)
    now: datetime = datetime(2020, 1, 2, 3, 4)
    rsp_params = RequestStateParameters(aggregator_id, None)

    mock_select_single_site_with_sfdi.return_value = None
    mock_EndDeviceMapper.map_from_request = mock.Mock(return_value=mapped_site)
    mock_upsert_site_for_aggregator.return_value = 4321
    mock_datetime.now = mock.Mock(return_value=now)

    # Act
    returned_site_id = await EndDeviceManager.add_or_update_enddevice_for_aggregator(
        mock_session, rsp_params, end_device
    )
    assert returned_site_id == mock_upsert_site_for_aggregator.return_value

    # Assert
    assert_mock_session(mock_session, committed=True)
    mock_EndDeviceMapper.map_from_request.assert_called_once_with(end_device, aggregator_id, now)
    assert mock_EndDeviceMapper.map_from_request.call_args[0][0].sFDI != 0, "sfdi should be regenerated"
    assert mock_EndDeviceMapper.map_from_request.call_args[0][0].lFDI != "", "lfdi should be regenerated"
    mock_upsert_site_for_aggregator.assert_called_once_with(mock_session, aggregator_id, mapped_site)
    mock_datetime.now.assert_called_once()
    mock_select_single_site_with_sfdi.assert_called_once()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_all_sites_with_aggregator_id")
@mock.patch("envoy.server.manager.end_device.select_aggregator_site_count")
@mock.patch("envoy.server.manager.end_device.EndDeviceListMapper")
async def test_fetch_enddevicelist_with_aggregator_id(
    mock_EndDeviceListMapper: mock.MagicMock,
    mock_select_aggregator_site_count: mock.MagicMock,
    mock_select_all_sites_with_aggregator_id: mock.MagicMock,
):
    """Checks that fetching the enddevice list just passes through to the relevant CRUD"""
    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 3
    start = 4
    after = datetime.now()
    limit = 5
    mapped_ed_list: EndDeviceListResponse = generate_class_instance(EndDeviceListResponse)
    returned_site_count = 123
    returned_sites: list[Site] = [
        generate_class_instance(Site, seed=101, optional_is_none=False),
        generate_class_instance(Site, seed=202, optional_is_none=True),
    ]
    rsp_params = RequestStateParameters(aggregator_id, None)

    mock_EndDeviceListMapper.map_to_response = mock.Mock(return_value=mapped_ed_list)
    mock_select_all_sites_with_aggregator_id.return_value = returned_sites
    mock_select_aggregator_site_count.return_value = returned_site_count

    # Act
    result: EndDeviceListResponse = await EndDeviceListManager.fetch_enddevicelist_with_aggregator_id(
        mock_session, rsp_params, start, after, limit
    )

    # Assert
    assert result is mapped_ed_list
    assert_mock_session(mock_session, committed=False)

    mock_EndDeviceListMapper.map_to_response.assert_called_once_with(rsp_params, returned_sites, returned_site_count)
    mock_select_all_sites_with_aggregator_id.assert_called_once_with(mock_session, aggregator_id, start, after, limit)
    mock_select_aggregator_site_count.assert_called_once_with(mock_session, aggregator_id, after)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_all_sites_with_aggregator_id")
@mock.patch("envoy.server.manager.end_device.select_aggregator_site_count")
@mock.patch("envoy.server.manager.end_device.EndDeviceListMapper")
async def test_fetch_enddevicelist_with_aggregator_id_empty_list(
    mock_EndDeviceListMapper: mock.MagicMock,
    mock_select_aggregator_site_count: mock.MagicMock,
    mock_select_all_sites_with_aggregator_id: mock.MagicMock,
):
    """Checks that fetching the enddevice list just passes through to the relevant CRUD
    even when empty list is returned"""
    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 3
    start = 4
    after = datetime.now()
    limit = 5
    mapped_ed_list: EndDeviceListResponse = generate_class_instance(EndDeviceListResponse)
    returned_site_count = 123
    returned_sites: list[Site] = []
    rsp_params = RequestStateParameters(aggregator_id, None)

    mock_EndDeviceListMapper.map_to_response = mock.Mock(return_value=mapped_ed_list)
    mock_select_all_sites_with_aggregator_id.return_value = returned_sites
    mock_select_aggregator_site_count.return_value = returned_site_count

    # Act
    result: EndDeviceListResponse = await EndDeviceListManager.fetch_enddevicelist_with_aggregator_id(
        mock_session, rsp_params, start, after, limit
    )

    # Assert
    assert result is mapped_ed_list
    assert_mock_session(mock_session, committed=False)

    mock_EndDeviceListMapper.map_to_response.assert_called_once_with(rsp_params, returned_sites, returned_site_count)
    mock_select_all_sites_with_aggregator_id.assert_called_once_with(mock_session, aggregator_id, start, after, limit)
    mock_select_aggregator_site_count.assert_called_once_with(mock_session, aggregator_id, after)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.end_device.ConnectionPointMapper")
async def test_end_device_manager_fetch_existing_connection_point(
    mock_ConnectionPointMapper: mock.MagicMock, mock_select_single_site_with_site_id: mock.MagicMock
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    site_id = 1
    aggregator_id = 2
    raw_site: Site = generate_class_instance(Site)
    mapped_cp: ConnectionPointResponse = generate_class_instance(ConnectionPointResponse)
    rsp_params = RequestStateParameters(aggregator_id, None)

    # Just do a simple passthrough
    mock_select_single_site_with_site_id.return_value = raw_site
    mock_ConnectionPointMapper.map_to_response = mock.Mock(return_value=mapped_cp)

    # Act
    result = await EndDeviceManager.fetch_connection_point_for_site(mock_session, site_id, rsp_params)

    # Assert
    assert result is mapped_cp
    assert_mock_session(mock_session, committed=False)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=site_id, aggregator_id=aggregator_id
    )
    mock_ConnectionPointMapper.map_to_response.assert_called_once_with(raw_site)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.end_device.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.end_device.ConnectionPointMapper")
async def test_end_device_manager_fetch_missing_connection_point(
    mock_ConnectionPointMapper: mock.MagicMock, mock_select_single_site_with_site_id: mock.MagicMock
):
    """Check that the manager will handle interacting with the DB and its responses when the
    requested site does not exist"""

    # Arrange
    mock_session = create_mock_session()
    site_id = 1
    aggregator_id = 2
    rsp_params = RequestStateParameters(aggregator_id, None)

    mock_select_single_site_with_site_id.return_value = None  # database entity is missing / bad ID lookup
    mock_ConnectionPointMapper.map_to_response = mock.Mock()

    # Act
    result = await EndDeviceManager.fetch_connection_point_for_site(mock_session, site_id, rsp_params)

    # Assert
    assert result is None
    assert_mock_session(mock_session, committed=False)
    mock_select_single_site_with_site_id.assert_called_once_with(
        session=mock_session, site_id=site_id, aggregator_id=aggregator_id
    )
    mock_ConnectionPointMapper.map_to_response.assert_not_called()  # Don't map if there's nothing in the DB
