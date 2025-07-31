import unittest.mock as mock
from datetime import datetime
from itertools import product
from typing import Optional

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.asyncio import create_async_result
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.metering import ReadingType
from envoy_schema.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorMeterReadingListRequest,
    MirrorMeterReadingRequest,
    MirrorReadingSet,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
    Reading,
)
from envoy_schema.server.schema.sep2.types import DateTimeIntervalType
from sqlalchemy import func, select

from envoy.server.crud.site_reading import GroupedSiteReadingTypeDetails
from envoy.server.exception import BadRequestError, ForbiddenError, InvalidIdError, NotFoundError
from envoy.server.manager.metering import MirrorMeteringManager
from envoy.server.model.archive.site_reading import ArchiveSiteReadingType
from envoy.server.model.config.server import RuntimeServerConfig
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import CertificateType, MUPRequestScope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.metering.upsert_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper")
async def test_create_or_fetch_mirror_usage_point_aggregator(
    mock_MirrorUsagePointMapper: mock.MagicMock,
    mock_upsert_site_reading_type_for_aggregator: mock.MagicMock,
    mock_select_single_site_with_lfdi: mock.MagicMock,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    existing_site: Site = generate_class_instance(Site)
    mapped_srt: SiteReadingType = generate_class_instance(SiteReadingType)
    srt_id = 3
    scope: MUPRequestScope = generate_class_instance(MUPRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE)

    mock_select_single_site_with_lfdi.return_value = existing_site
    mock_MirrorUsagePointMapper.map_from_request = mock.Mock(return_value=mapped_srt)
    mock_upsert_site_reading_type_for_aggregator.return_value = srt_id

    # Act
    result = await MirrorMeteringManager.create_or_update_mirror_usage_point(mock_session, scope, mup)

    # Assert
    assert result == srt_id
    assert_mock_session(mock_session, committed=True)
    mock_select_single_site_with_lfdi.assert_called_once_with(
        session=mock_session, lfdi=mup.deviceLFDI, aggregator_id=scope.aggregator_id
    )
    mock_upsert_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=scope.aggregator_id, site_reading_type=mapped_srt
    )

    mock_MirrorUsagePointMapper.map_from_request.assert_called_once()
    mapper_call_args = mock_MirrorUsagePointMapper.map_from_request.call_args_list[0]
    assert mapper_call_args.kwargs["aggregator_id"] == scope.aggregator_id
    assert mapper_call_args.kwargs["site_id"] == existing_site.site_id
    assert_nowish(mapper_call_args.kwargs["changed_time"])


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_lfdi")
@mock.patch("envoy.server.manager.metering.upsert_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper")
@pytest.mark.parametrize("scope_site_id, request_lfdi", product([None, 123], ["abc123DEF", "abc123def"]))
async def test_create_or_fetch_mirror_usage_point_device(
    mock_MirrorUsagePointMapper: mock.MagicMock,
    mock_upsert_site_reading_type_for_aggregator: mock.MagicMock,
    mock_select_single_site_with_lfdi: mock.MagicMock,
    scope_site_id: Optional[int],
    request_lfdi: str,
):
    """Check that the manager will handle interacting with the DB and its responses (when handling a valid device
    cert)"""

    # Arrange
    mock_session = create_mock_session()
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint, deviceLFDI=request_lfdi)
    existing_site: Site = generate_class_instance(Site)
    mapped_srt: SiteReadingType = generate_class_instance(SiteReadingType)
    srt_id = 3
    scope: MUPRequestScope = generate_class_instance(
        MUPRequestScope,
        source=CertificateType.DEVICE_CERTIFICATE,
        site_id=scope_site_id,
        lfdi=request_lfdi.lower(),  # scope lfdis are always lowercase
    )

    mock_select_single_site_with_lfdi.return_value = existing_site
    mock_MirrorUsagePointMapper.map_from_request = mock.Mock(return_value=mapped_srt)
    mock_upsert_site_reading_type_for_aggregator.return_value = srt_id

    # Act
    result = await MirrorMeteringManager.create_or_update_mirror_usage_point(mock_session, scope, mup)

    # Assert
    assert result == srt_id
    assert_mock_session(mock_session, committed=True)
    mock_select_single_site_with_lfdi.assert_called_once_with(
        session=mock_session, lfdi=mup.deviceLFDI.lower(), aggregator_id=scope.aggregator_id
    )
    mock_upsert_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=scope.aggregator_id, site_reading_type=mapped_srt
    )

    mock_MirrorUsagePointMapper.map_from_request.assert_called_once()
    mapper_call_args = mock_MirrorUsagePointMapper.map_from_request.call_args_list[0]
    assert mapper_call_args.kwargs["aggregator_id"] == scope.aggregator_id
    assert mapper_call_args.kwargs["site_id"] == existing_site.site_id
    assert_nowish(mapper_call_args.kwargs["changed_time"])


@pytest.mark.anyio
async def test_create_or_fetch_mirror_usage_point_device_bad_lfdi():
    """Check that the manager will raise Forbidden Errors when the LFDI mismatches the client LFDI"""

    # Arrange
    mock_session = create_mock_session()
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    scope: MUPRequestScope = generate_class_instance(
        MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, lfdi=mup.deviceLFDI + "diff"
    )

    # Act
    with pytest.raises(ForbiddenError):
        await MirrorMeteringManager.create_or_update_mirror_usage_point(mock_session, scope, mup)

    # Assert
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_lfdi")
async def test_create_or_fetch_mirror_usage_point_aggregator_no_site(mock_select_single_site_with_lfdi: mock.MagicMock):
    """Check that the manager will handle the case when the referenced site DNE"""

    # Arrange
    mock_session = create_mock_session()
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    scope: MUPRequestScope = generate_class_instance(MUPRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE)

    mock_select_single_site_with_lfdi.return_value = None

    # Act
    with pytest.raises(InvalidIdError):
        await MirrorMeteringManager.create_or_update_mirror_usage_point(mock_session, scope, mup)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_select_single_site_with_lfdi.assert_called_once_with(
        session=mock_session,
        lfdi=mup.deviceLFDI,
        aggregator_id=scope.aggregator_id,
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_lfdi")
@pytest.mark.parametrize("scope_site_id", [None, 123])
async def test_create_or_fetch_mirror_usage_point_device_no_site(
    mock_select_single_site_with_lfdi: mock.MagicMock, scope_site_id: Optional[int]
):
    """Check that the manager will handle the case when the referenced site DNE"""

    # Arrange
    mock_session = create_mock_session()
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    scope: MUPRequestScope = generate_class_instance(
        MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, lfdi=mup.deviceLFDI
    )

    mock_select_single_site_with_lfdi.return_value = None

    # Act
    with pytest.raises(InvalidIdError):
        await MirrorMeteringManager.create_or_update_mirror_usage_point(mock_session, scope, mup)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_select_single_site_with_lfdi.assert_called_once_with(
        session=mock_session,
        lfdi=mup.deviceLFDI,
        aggregator_id=scope.aggregator_id,
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.metering.fetch_site_reading_types_for_group")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper.map_to_response")
@mock.patch("envoy.server.manager.end_device.RuntimeServerConfigManager.fetch_current_config")
@pytest.mark.parametrize(
    "cert_type, scope_site_id",
    product([CertificateType.AGGREGATOR_CERTIFICATE, CertificateType.DEVICE_CERTIFICATE], [123, None]),
)
async def test_fetch_mirror_usage_point(
    mock_fetch_current_config: mock.MagicMock,
    mock_map_to_response: mock.MagicMock,
    mock_fetch_site_reading_types_for_group: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    cert_type: CertificateType,
    scope_site_id: Optional[int],
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    mup_id = 3
    mapped_mup = generate_class_instance(MirrorUsagePoint)
    site_id = scope_site_id if scope_site_id is not None else 123321
    srts = [
        generate_class_instance(SiteReadingType, seed=101, optional_is_none=True, site_id=site_id),
        generate_class_instance(SiteReadingType, seed=202, optional_is_none=False, site_id=site_id),
    ]
    site = generate_class_instance(Site, seed=303, site_id=site_id)
    scope = generate_class_instance(MUPRequestScope, source=cert_type, site_id=scope_site_id)

    mock_fetch_site_reading_types_for_group.return_value = srts
    mock_select_single_site_with_site_id.return_value = site
    mock_map_to_response.return_value = mapped_mup

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    result = await MirrorMeteringManager.fetch_mirror_usage_point(mock_session, scope, mup_id)

    # Assert
    assert result is mapped_mup
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_types_for_group.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        group_id=mup_id,
    )
    mock_select_single_site_with_site_id.assert_called_once_with(
        mock_session, site_id=site_id, aggregator_id=scope.aggregator_id
    )
    mock_map_to_response.assert_called_once()
    assert mock_map_to_response.call_args_list[0].args[0] == scope
    assert mock_map_to_response.call_args_list[0].args[1].group_id == mup_id
    assert mock_map_to_response.call_args_list[0].args[1].site_lfdi == site.lfdi
    assert mock_map_to_response.call_args_list[0].args[2] == srts
    assert mock_map_to_response.call_args_list[0].args[3] == config.mup_postrate_seconds


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.metering.fetch_site_reading_types_for_group")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper.map_to_response")
@mock.patch("envoy.server.manager.end_device.RuntimeServerConfigManager.fetch_current_config")
@pytest.mark.parametrize(
    "cert_type, scope_site_id",
    product([CertificateType.AGGREGATOR_CERTIFICATE, CertificateType.DEVICE_CERTIFICATE], [123, None]),
)
async def test_fetch_mirror_usage_point_no_srts(
    mock_fetch_current_config: mock.MagicMock,
    mock_map_to_response: mock.MagicMock,
    mock_fetch_site_reading_types_for_group: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    cert_type: CertificateType,
    scope_site_id: Optional[int],
):
    """Check that the manager will raise a NotFoundError if there are no SiteReadingTypes with that mup id"""

    # Arrange
    mock_session = create_mock_session()
    mup_id = 3
    srts = []
    scope = generate_class_instance(MUPRequestScope, source=cert_type, site_id=scope_site_id)

    mock_fetch_site_reading_types_for_group.return_value = srts

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    with pytest.raises(NotFoundError):
        await MirrorMeteringManager.fetch_mirror_usage_point(mock_session, scope, mup_id)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_types_for_group.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        group_id=mup_id,
    )
    mock_select_single_site_with_site_id.assert_not_called()
    mock_map_to_response.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.metering.fetch_site_reading_types_for_group")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper.map_to_response")
@mock.patch("envoy.server.manager.end_device.RuntimeServerConfigManager.fetch_current_config")
@pytest.mark.parametrize(
    "cert_type, scope_site_id",
    product([CertificateType.AGGREGATOR_CERTIFICATE, CertificateType.DEVICE_CERTIFICATE], [123, None]),
)
async def test_fetch_mirror_usage_point_no_site(
    mock_fetch_current_config: mock.MagicMock,
    mock_map_to_response: mock.MagicMock,
    mock_fetch_site_reading_types_for_group: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    cert_type: CertificateType,
    scope_site_id: Optional[int],
):
    """Check that the manager will raise a NotFoundError if the linked site can't be accessed"""

    # Arrange
    mock_session = create_mock_session()
    mup_id = 3
    site_id = scope_site_id if scope_site_id is not None else 123321
    srts = [
        generate_class_instance(SiteReadingType, seed=101, optional_is_none=True, site_id=site_id),
    ]
    scope = generate_class_instance(MUPRequestScope, source=cert_type, site_id=scope_site_id)

    mock_fetch_site_reading_types_for_group.return_value = srts
    mock_select_single_site_with_site_id.return_value = None

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    with pytest.raises(NotFoundError):
        await MirrorMeteringManager.fetch_mirror_usage_point(mock_session, scope, mup_id)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_types_for_group.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        group_id=mup_id,
    )
    mock_select_single_site_with_site_id.assert_called_once_with(
        mock_session, site_id=site_id, aggregator_id=scope.aggregator_id
    )
    mock_map_to_response.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("return_value, site_id", product([True, False], [99987, None]))
@mock.patch("envoy.server.manager.metering.delete_site_reading_type_group")
@mock.patch("envoy.server.manager.metering.utc_now")
@mock.patch("envoy.server.manager.metering.NotificationManager")
async def test_delete_mirror_usage_point(
    mock_NotificationManager: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
    mock_delete_site_reading_type_group: mock.MagicMock,
    return_value: bool,
    site_id: Optional[int],
):
    """Check that the manager will handle interacting with the crud layer / managing the session transaction"""

    # Arrange
    mock_session = create_mock_session()
    scope: MUPRequestScope = generate_class_instance(MUPRequestScope, site_id=site_id)
    delete_time = datetime(2021, 5, 6, 7, 8, 9)
    mup_id = 151512
    mock_NotificationManager.notify_changed_deleted_entities = mock.Mock(return_value=create_async_result(True))

    # Just do a simple passthrough
    mock_utc_now.return_value = delete_time
    mock_delete_site_reading_type_group.return_value = return_value

    # Act
    result = await MirrorMeteringManager.delete_mirror_usage_point(mock_session, scope, mup_id)

    # Assert
    assert result == return_value
    assert_mock_session(mock_session, committed=True)  # The session WILL be committed
    mock_delete_site_reading_type_group.assert_called_once_with(
        mock_session,
        site_id=scope.site_id,
        group_id=mup_id,
        aggregator_id=scope.aggregator_id,
        deleted_time=delete_time,
    )
    mock_utc_now.assert_called_once()
    mock_NotificationManager.notify_changed_deleted_entities.assert_called_once_with(
        SubscriptionResource.READING, delete_time
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_types_for_group")
@mock.patch("envoy.server.manager.metering.fetch_grouped_site_reading_details")
@mock.patch("envoy.server.manager.metering.count_grouped_site_reading_details")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointListMapper")
@mock.patch("envoy.server.manager.end_device.RuntimeServerConfigManager.fetch_current_config")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=None),
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=123),
        generate_class_instance(MUPRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE, site_id=123),
    ],
)
async def test_list_mirror_usage_points(
    mock_fetch_current_config: mock.MagicMock,
    mock_MirrorUsagePointListMapper: mock.MagicMock,
    mock_count_grouped_site_reading_details: mock.MagicMock,
    mock_fetch_grouped_site_reading_details: mock.MagicMock,
    mock_fetch_site_reading_types_for_group: mock.MagicMock,
    scope: MUPRequestScope,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    count = 456
    start = 4
    limit = 5
    changed_after = datetime.now()
    groups = [
        generate_class_instance(GroupedSiteReadingTypeDetails, seed=101),
        generate_class_instance(GroupedSiteReadingTypeDetails, seed=202),
    ]
    srts_group_1 = [generate_class_instance(SiteReadingType, seed=303)]
    srts_group_2 = [
        generate_class_instance(SiteReadingType, seed=404),
        generate_class_instance(SiteReadingType, seed=505),
    ]
    mup_response = generate_class_instance(MirrorUsagePointListResponse)

    mock_fetch_site_reading_types_for_group.side_effect = [srts_group_1, srts_group_2]
    mock_count_grouped_site_reading_details.return_value = count
    mock_fetch_grouped_site_reading_details.return_value = groups
    mock_MirrorUsagePointListMapper.map_to_list_response = mock.Mock(return_value=mup_response)

    config = RuntimeServerConfig()
    mock_fetch_current_config.return_value = config

    # Act
    result = await MirrorMeteringManager.list_mirror_usage_points(mock_session, scope, start, limit, changed_after)
    assert result is mup_response

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_grouped_site_reading_details.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        start=start,
        changed_after=changed_after,
        limit=limit,
    )
    mock_count_grouped_site_reading_details.assert_called_once_with(
        mock_session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, changed_after=changed_after
    )
    mock_fetch_site_reading_types_for_group.assert_has_calls(
        [
            mock.call(
                mock_session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, group_id=groups[0].group_id
            ),
            mock.call(
                mock_session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, group_id=groups[1].group_id
            ),
        ]
    )

    mock_MirrorUsagePointListMapper.map_to_list_response.assert_called_once_with(
        scope, count, [(groups[0], srts_group_1), (groups[1], srts_group_2)], config.mup_postrate_seconds
    )


@pytest.mark.parametrize("agg_id, site_id, mup_id", [(99, 1, 1), (1, 99, 1), (1, 1, 99), (1, 1, 4)])
@pytest.mark.anyio
async def test_add_or_update_readings_no_mup_id(pg_base_config, agg_id, site_id, mup_id):
    """Requesting a mup ID that is out of scope for the client will generate an error"""
    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(NotFoundError):
            await MirrorMeteringManager.add_or_update_readings(
                session,
                MUPRequestScope("", 1, None, 0, CertificateType.AGGREGATOR_CERTIFICATE, agg_id, 0, site_id),
                mup_id,
                generate_class_instance(MirrorMeterReadingRequest),
            )


@pytest.mark.parametrize(
    "agg_id, site_id, mup_id, payload",
    [
        (
            1,
            1,
            1,
            generate_class_instance(MirrorMeterReadingRequest, mRID="abc123"),
        ),  # mrid mismatch AND no readingType
        (1, 1, 1, generate_class_instance(MirrorMeterReadingListRequest, mirrorMeterReadings=None)),  # nothing to do
        (1, 1, 1, generate_class_instance(MirrorMeterReadingListRequest, mirrorMeterReadings=[])),  # nothing to do
    ],
)
@pytest.mark.anyio
async def test_add_or_update_readings_bad_request(pg_base_config, agg_id, site_id, mup_id, payload):
    """Highlights the various ways an incoming request can be malformed"""
    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(BadRequestError):
            await MirrorMeteringManager.add_or_update_readings(
                session,
                MUPRequestScope("", 1, None, 0, CertificateType.AGGREGATOR_CERTIFICATE, agg_id, 0, site_id),
                mup_id,
                payload,
            )


@pytest.mark.parametrize("as_list", [True, False])
@pytest.mark.anyio
async def test_add_or_update_readings_no_readings_mup_update(pg_base_config, as_list: bool):
    """Tests that a payload with no readings but a MUP update works and archives appropriately"""

    rt = generate_class_instance(ReadingType)
    mmr = generate_class_instance(
        MirrorMeterReadingRequest,
        mRID="50000000000000000000000000000abc",
        readingType=rt,
    )
    if as_list:
        payload = generate_class_instance(MirrorMeterReadingListRequest, mirrorMeterReadings=[mmr])
    else:
        payload = mmr
    mup_id = 1

    # Act
    async with generate_async_session(pg_base_config) as session:
        await MirrorMeteringManager.add_or_update_readings(
            session,
            MUPRequestScope("", 1, None, 0, CertificateType.AGGREGATOR_CERTIFICATE, 1, 0, 1),
            mup_id,
            payload,
        )
        await session.commit()

    # Assert
    async with generate_async_session(pg_base_config) as session:
        archive_srts = (await session.execute(select(ArchiveSiteReadingType))).scalars().all()
        assert len(archive_srts) == 1
        assert archive_srts[0].site_reading_type_id == 5, "The original DB value"
        assert archive_srts[0].power_of_ten_multiplier == 3, "The original DB value"
        assert archive_srts[0].uom == 38, "The original DB value"

        updated_srt = (
            await session.execute(select(SiteReadingType).where(SiteReadingType.site_reading_type_id == 5))
        ).scalar_one()
        assert updated_srt.uom == mmr.readingType.uom
        assert updated_srt.power_of_ten_multiplier == mmr.readingType.powerOfTenMultiplier


@pytest.mark.parametrize("as_list", [True, False])
@pytest.mark.anyio
async def test_add_or_update_readings_no_readings_mup_insert(pg_base_config, as_list: bool):
    """Tests that a payload with no readings but a MUP update works and archives appropriately"""

    rt = generate_class_instance(ReadingType)
    mmr = generate_class_instance(
        MirrorMeterReadingRequest,
        mRID="6def",  # new mrid
        readingType=rt,
    )
    if as_list:
        payload = generate_class_instance(MirrorMeterReadingListRequest, mirrorMeterReadings=[mmr])
    else:
        payload = mmr
    mup_id = 1

    # Act
    async with generate_async_session(pg_base_config) as session:
        await MirrorMeteringManager.add_or_update_readings(
            session,
            MUPRequestScope("", 1, None, 0, CertificateType.AGGREGATOR_CERTIFICATE, 1, 0, 1),
            mup_id,
            payload,
        )
        await session.commit()

    # Assert
    async with generate_async_session(pg_base_config) as session:
        archive_srts = (await session.execute(select(ArchiveSiteReadingType))).scalars().all()
        assert len(archive_srts) == 0, "Nothing should archive - we are creating a new SiteReadingType"

        new_srt = (
            await session.execute(
                select(SiteReadingType).order_by(SiteReadingType.site_reading_type_id.desc()).limit(1)
            )
        ).scalar_one()
        assert_nowish(new_srt.changed_time)
        assert_nowish(new_srt.created_time)
        assert new_srt.uom == mmr.readingType.uom
        assert new_srt.power_of_ten_multiplier == mmr.readingType.powerOfTenMultiplier
        assert new_srt.role_flags == 1, "Inherited from other SiteReadingTypes in group"
        assert new_srt.group_id == 1, "Inherited from other SiteReadingTypes in group"
        assert new_srt.site_id == 1, "Inherited from other SiteReadingTypes in group"
        assert new_srt.aggregator_id == 1, "Inherited from other SiteReadingTypes in group"


@pytest.mark.anyio
async def test_add_or_update_readings_multiple_readings_no_mup_updates(pg_base_config):
    """Tests that a payload with multiple readings can write when there are no mup updates"""

    reading1 = generate_class_instance(
        Reading,
        seed=1,
        qualityFlags="",
        localID="ab",
        timePeriod=generate_class_instance(DateTimeIntervalType, seed=101),
    )
    reading2 = generate_class_instance(
        Reading,
        seed=2,
        qualityFlags="",
        localID="02",
        timePeriod=generate_class_instance(DateTimeIntervalType, seed=202),
    )
    reading3 = generate_class_instance(
        Reading,
        seed=3,
        qualityFlags="",
        localID="c1",
        timePeriod=generate_class_instance(DateTimeIntervalType, seed=303),
    )

    mmr1 = generate_class_instance(
        MirrorMeterReadingRequest,
        mRID="10000000000000000000000000000abc",  # matches SiteReadingType 1
        readingType=generate_class_instance(
            ReadingType,
            dataQualifier=2,
            uom=38,
            flowDirection=1,
            accumulationBehaviour=3,
            kind=37,
            phase=64,
            powerOfTenMultiplier=3,
            intervalLength=0,
        ),  # Matches SiteReadingType #1 perfectly so no update required
        reading=reading1,
    )

    mmr5 = generate_class_instance(
        MirrorMeterReadingRequest,
        mRID="50000000000000000000000000000abc",  # matches SiteReadingType 5
        readingType=None,
        mirrorReadingSets=[generate_class_instance(MirrorReadingSet, readings=[reading2, reading3])],
    )

    payload = generate_class_instance(MirrorMeterReadingListRequest, mirrorMeterReadings=[mmr1, mmr5])
    mup_id = 1

    # Act
    async with generate_async_session(pg_base_config) as session:
        await MirrorMeteringManager.add_or_update_readings(
            session,
            MUPRequestScope("", 1, None, 0, CertificateType.AGGREGATOR_CERTIFICATE, 1, 0, 1),
            mup_id,
            payload,
        )
        await session.commit()

    # Assert
    async with generate_async_session(pg_base_config) as session:
        archive_srts = (await session.execute(select(ArchiveSiteReadingType))).scalars().all()
        assert len(archive_srts) == 0, "Nothing should archive - we are adding readings"

        new_readings = (
            (await session.execute(select(SiteReading).order_by(SiteReading.site_reading_id.desc()).limit(3)))
            .scalars()
            .all()
        )
        assert len(new_readings) == 3
        for db_reading, src_reading in zip(new_readings, [reading3, reading2, reading1]):
            assert_nowish(db_reading.changed_time)
            assert_nowish(db_reading.created_time)
            assert db_reading.value == src_reading.value
            assert db_reading.local_id == int(src_reading.localID, 16)
