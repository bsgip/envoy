import unittest.mock as mock
from datetime import datetime

import pytest
from envoy_schema.server.schema.sep2.metering_mirror import MirrorMeterReading, MirrorUsagePoint
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.api.request import RequestStateParameters
from envoy.server.exception import InvalidIdError, NotFoundError
from envoy.server.manager.metering import MirrorMeteringManager
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from tests.assert_time import assert_nowish
from tests.data.fake.generator import generate_class_instance
from tests.unit.mocks import assert_mock_session, create_mock_session


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.metering.upsert_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper")
async def test_create_or_fetch_mirror_usage_point(
    mock_MirrorUsagePointMapper: mock.MagicMock,
    mock_upsert_site_reading_type_for_aggregator: mock.MagicMock,
    mock_select_single_site_with_lfdi: mock.MagicMock,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 2
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    existing_site: Site = generate_class_instance(Site)
    mapped_srt: SiteReadingType = generate_class_instance(SiteReadingType)
    srt_id = 3
    rs_params = RequestStateParameters(aggregator_id, None)

    mock_select_single_site_with_lfdi.return_value = existing_site
    mock_MirrorUsagePointMapper.map_from_request = mock.Mock(return_value=mapped_srt)
    mock_upsert_site_reading_type_for_aggregator.return_value = srt_id

    # Act
    result = await MirrorMeteringManager.create_or_update_mirror_usage_point(mock_session, rs_params, mup)

    # Assert
    assert result == srt_id
    assert_mock_session(mock_session, committed=True)
    mock_select_single_site_with_lfdi.assert_called_once_with(
        session=mock_session, lfdi=mup.deviceLFDI, aggregator_id=aggregator_id
    )
    mock_upsert_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=aggregator_id, site_reading_type=mapped_srt
    )

    mock_MirrorUsagePointMapper.map_from_request.assert_called_once()
    mapper_call_args = mock_MirrorUsagePointMapper.map_from_request.call_args_list[0]
    assert mapper_call_args.kwargs["aggregator_id"] == aggregator_id
    assert mapper_call_args.kwargs["site_id"] == existing_site.site_id
    assert_nowish(mapper_call_args.kwargs["changed_time"])


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_lfdi")
async def test_create_or_fetch_mirror_usage_point_no_site(mock_select_single_site_with_lfdi: mock.MagicMock):
    """Check that the manager will handle the case when the referenced site DNE"""

    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 2
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    rs_params = RequestStateParameters(aggregator_id, None)

    mock_select_single_site_with_lfdi.return_value = None

    # Act
    with pytest.raises(InvalidIdError):
        await MirrorMeteringManager.create_or_update_mirror_usage_point(mock_session, rs_params, mup)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_select_single_site_with_lfdi.assert_called_once_with(
        session=mock_session,
        lfdi=mup.deviceLFDI,
        aggregator_id=aggregator_id,
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper")
async def test_fetch_mirror_usage_point(
    mock_MirrorUsagePointMapper: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 2
    srt_id = 3
    mapped_mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    existing_srt: SiteReadingType = generate_class_instance(SiteReadingType)
    existing_srt.site = generate_class_instance(Site)
    rs_params = RequestStateParameters(aggregator_id, None)

    mock_fetch_site_reading_type_for_aggregator.return_value = existing_srt
    mock_MirrorUsagePointMapper.map_to_response = mock.Mock(return_value=mapped_mup)

    # Act
    result = await MirrorMeteringManager.fetch_mirror_usage_point(mock_session, rs_params, srt_id)

    # Assert
    assert result is mapped_mup
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=aggregator_id, site_reading_type_id=srt_id, include_site_relation=True
    )
    mock_MirrorUsagePointMapper.map_to_response.assert_called_once_with(rs_params, existing_srt, existing_srt.site)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
async def test_fetch_mirror_usage_point_no_srt(
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 2
    srt_id = 3
    rs_params = RequestStateParameters(aggregator_id, None)

    mock_fetch_site_reading_type_for_aggregator.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await MirrorMeteringManager.fetch_mirror_usage_point(mock_session, rs_params, srt_id)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=aggregator_id, site_reading_type_id=srt_id, include_site_relation=True
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.upsert_site_readings")
@mock.patch("envoy.server.manager.metering.MirrorMeterReadingMapper")
async def test_add_or_update_readings(
    mock_MirrorMeterReadingMapper: mock.MagicMock,
    mock_upsert_site_readings: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 2
    site_reading_type_id = 3
    mmr: MirrorMeterReading = generate_class_instance(MirrorMeterReading, seed=101)
    existing_sr: SiteReadingType = generate_class_instance(SiteReadingType, seed=202)
    mapped_readings: list[SiteReading] = [generate_class_instance(SiteReading, seed=303)]
    rs_params = RequestStateParameters(aggregator_id, None)

    mock_fetch_site_reading_type_for_aggregator.return_value = existing_sr
    mock_MirrorMeterReadingMapper.map_from_request = mock.Mock(return_value=mapped_readings)

    # Act
    await MirrorMeteringManager.add_or_update_readings(mock_session, rs_params, site_reading_type_id, mmr)

    # Assert
    assert_mock_session(mock_session, committed=True)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session,
        aggregator_id=aggregator_id,
        site_reading_type_id=site_reading_type_id,
        include_site_relation=False,
    )
    mock_upsert_site_readings.assert_called_once_with(mock_session, mapped_readings)

    mock_MirrorMeterReadingMapper.map_from_request.assert_called_once()
    mapper_call_args = mock_MirrorMeterReadingMapper.map_from_request.call_args_list[0]
    assert mapper_call_args.kwargs["aggregator_id"] == aggregator_id
    assert mapper_call_args.kwargs["site_reading_type_id"] == site_reading_type_id
    assert_nowish(mapper_call_args.kwargs["changed_time"])


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
async def test_add_or_update_readings_no_srt(mock_fetch_site_reading_type_for_aggregator: mock.MagicMock):
    """Check that the manager will handle the case where the site reading type DNE"""

    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 2
    site_reading_type_id = 3
    mmr: MirrorMeterReading = generate_class_instance(MirrorMeterReading, seed=101)
    rs_params = RequestStateParameters(aggregator_id, None)

    mock_fetch_site_reading_type_for_aggregator.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await MirrorMeteringManager.add_or_update_readings(mock_session, rs_params, site_reading_type_id, mmr)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session,
        aggregator_id=aggregator_id,
        site_reading_type_id=site_reading_type_id,
        include_site_relation=False,
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_types_page_for_aggregator")
@mock.patch("envoy.server.manager.metering.count_site_reading_types_for_aggregator")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointListMapper")
async def test_list_mirror_usage_points(
    mock_MirrorUsagePointListMapper: mock.MagicMock,
    mock_count_site_reading_types_for_aggregator: mock.MagicMock,
    mock_fetch_site_reading_types_page_for_aggregator: mock.MagicMock,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    aggregator_id = 2
    count = 456
    start = 4
    limit = 5
    changed_after = datetime.now()
    existing_srts: list[SiteReadingType] = [generate_class_instance(SiteReadingType, seed=101)]
    mup_response: list[SiteReading] = [generate_class_instance(SiteReading, seed=202)]
    rs_params = RequestStateParameters(aggregator_id, None)

    mock_count_site_reading_types_for_aggregator.return_value = count
    mock_fetch_site_reading_types_page_for_aggregator.return_value = existing_srts
    mock_MirrorUsagePointListMapper.map_to_list_response = mock.Mock(return_value=mup_response)

    # Act
    result = await MirrorMeteringManager.list_mirror_usage_points(mock_session, rs_params, start, limit, changed_after)
    assert result is mup_response

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_types_page_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=aggregator_id, start=start, limit=limit, changed_after=changed_after
    )
    mock_count_site_reading_types_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=aggregator_id, changed_after=changed_after
    )

    mock_MirrorUsagePointListMapper.map_to_list_response.assert_called_once_with(rs_params, existing_srts, count)
