import unittest.mock as mock
from datetime import datetime

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.log_events import LogEvent, LogEventList
from sqlalchemy import func, select

from envoy.server.exception import NotFoundError
from envoy.server.manager.log_event import LogEventManager
from envoy.server.model.site import Site, SiteLogEvent
from envoy.server.request_scope import DeviceOrAggregatorRequestScope, SiteRequestScope


@mock.patch("envoy.server.manager.log_event.LogEventMapper.map_to_log_event")
@mock.patch("envoy.server.manager.log_event.select_log_event_for_scope")
@pytest.mark.anyio
async def test_fetch_log_event_for_scope_exists(
    mock_select_log_event_for_scope: mock.MagicMock,
    mock_map_to_log_event: mock.MagicMock,
):
    """Checks that fetching a log event that exists works OK"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    response_obj = generate_class_instance(SiteLogEvent)
    mapped_obj = generate_class_instance(LogEvent)
    mock_session = create_mock_session()
    response_id = 65314141

    mock_select_log_event_for_scope.return_value = response_obj
    mock_map_to_log_event.return_value = mapped_obj

    # Act
    result = await LogEventManager.fetch_log_event_for_scope(mock_session, scope, response_id)

    # Assert
    assert result is mapped_obj
    assert_mock_session(mock_session)
    mock_select_log_event_for_scope.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, response_id
    )
    mock_map_to_log_event.assert_called_once_with(scope, response_obj)


@mock.patch("envoy.server.manager.log_event.LogEventMapper.map_to_log_event")
@mock.patch("envoy.server.manager.log_event.select_log_event_for_scope")
@pytest.mark.anyio
async def test_fetch_log_event_for_scope_missing(
    mock_select_log_event_for_scope: mock.MagicMock,
    mock_map_to_log_event: mock.MagicMock,
):
    """Checks that fetching a log event that is missing works OK"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    mock_session = create_mock_session()
    response_id = 65314141

    mock_select_log_event_for_scope.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await LogEventManager.fetch_log_event_for_scope(mock_session, scope, response_id)

    # Assert
    assert_mock_session(mock_session)
    mock_select_log_event_for_scope.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, response_id
    )
    mock_map_to_log_event.assert_not_called()


@mock.patch("envoy.server.manager.log_event.LogEventListMapper.map_to_list_response")
@mock.patch("envoy.server.manager.log_event.select_site_log_events")
@mock.patch("envoy.server.manager.log_event.count_site_log_events")
@pytest.mark.anyio
async def test_fetch_log_event_list_for_scope(
    mock_count_log_events: mock.MagicMock,
    mock_select_log_events: mock.MagicMock,
    mock_map_to_list_response: mock.MagicMock,
):
    """Checks that the flows for a response list work OK with DOEs"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    response_objs = [generate_class_instance(SiteLogEvent)]
    mapped_obj = generate_class_instance(LogEventList)
    mock_session = create_mock_session()
    start = 101
    limit = 202
    created_after = datetime(2022, 11, 1)
    mock_count = 67571

    mock_count_log_events.return_value = mock_count
    mock_select_log_events.return_value = response_objs
    mock_map_to_list_response.return_value = mapped_obj

    # Act
    result = await LogEventManager.fetch_log_event_list_for_scope(mock_session, scope, start, limit, created_after)

    # Assert
    assert result is mapped_obj
    assert_mock_session(mock_session)
    mock_select_log_events.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        start=start,
        limit=limit,
        created_after=created_after,
    )
    mock_count_log_events.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, created_after)
    mock_map_to_list_response.assert_called_once_with(scope, response_objs, mock_count)


@mock.patch("envoy.server.manager.log_event.select_single_site_with_site_id")
@pytest.mark.anyio
async def test_create_log_event_for_scope_site_dne(
    mock_select_single_site_with_site_id: mock.MagicMock,
):
    """Tests that log events will NOT be added to the DB if the site they reference DNE"""

    # Arrange
    site_id = 3  # Not accessible to this aggregator
    log_event = generate_class_instance(LogEvent)
    scope = generate_class_instance(SiteRequestScope, seed=101, site_id=site_id, href_prefix="/my_prefix/")
    mock_session = create_mock_session()

    mock_select_single_site_with_site_id.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await LogEventManager.create_log_event_for_scope(mock_session, scope, log_event)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(
        mock_session, aggregator_id=scope.aggregator_id, site_id=scope.site_id
    )

    assert_mock_session(mock_session, committed=False)


@mock.patch("envoy.server.manager.log_event.select_single_site_with_site_id")
@pytest.mark.anyio
async def test_create_log_event_for_scope_created_normally(
    mock_select_single_site_with_site_id: mock.MagicMock,
    pg_base_config,
):
    """Tests that log events can be added to the database and the appropriate href returned"""

    # Arrange
    site_id = 1
    log_event = generate_class_instance(LogEvent)
    scope = generate_class_instance(SiteRequestScope, seed=101, site_id=site_id, href_prefix="/my_prefix/")
    existing_site = generate_class_instance(Site, seed=303, site_id=site_id)

    mock_select_single_site_with_site_id.return_value = existing_site

    # Act
    async with generate_async_session(pg_base_config) as session:
        db_count_before = (await session.execute(select(func.count()).select_from(SiteLogEvent))).scalar_one()

    async with generate_async_session(pg_base_config) as session:
        returned_href = await LogEventManager.create_log_event_for_scope(session, scope, log_event)

    # Assert
    mock_select_single_site_with_site_id.assert_called_once_with(
        session, aggregator_id=scope.aggregator_id, site_id=scope.site_id
    )

    # Check the href looks valid and matches the new record in the DB
    assert isinstance(returned_href, str)
    assert returned_href.startswith(scope.href_prefix)
    new_id = int(returned_href.split("/")[-1])  # Assume LAST component of href is the DB ID
    async with generate_async_session(pg_base_config) as session:
        db_count_after = (await session.execute(select(func.count()).select_from(SiteLogEvent))).scalar_one()
        db_response = (
            await session.execute(select(SiteLogEvent).where(SiteLogEvent.site_log_event_id == new_id))
        ).scalar_one()

        assert db_count_after == (db_count_before + 1), "There should be a new response in the DB"
        assert db_response.site_id == site_id, "This is double checking the mapper"
        assert_nowish(db_response.created_time)
