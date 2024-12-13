import unittest.mock as mock
from datetime import datetime
from itertools import product
from typing import Optional

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.asyncio import create_async_result
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.metering_mirror import MirrorMeterReading, MirrorUsagePoint

from envoy.server.exception import ForbiddenError, InvalidIdError, NotFoundError
from envoy.server.manager.metering import MirrorMeteringManager
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
@pytest.mark.parametrize("scope_site_id", [None, 123])
async def test_create_or_fetch_mirror_usage_point_device(
    mock_MirrorUsagePointMapper: mock.MagicMock,
    mock_upsert_site_reading_type_for_aggregator: mock.MagicMock,
    mock_select_single_site_with_lfdi: mock.MagicMock,
    scope_site_id: Optional[int],
):
    """Check that the manager will handle interacting with the DB and its responses (when handling a valid device
    cert)"""

    # Arrange
    mock_session = create_mock_session()
    mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    existing_site: Site = generate_class_instance(Site)
    mapped_srt: SiteReadingType = generate_class_instance(SiteReadingType)
    srt_id = 3
    scope: MUPRequestScope = generate_class_instance(
        MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=scope_site_id, lfdi=mup.deviceLFDI
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
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointMapper")
@pytest.mark.parametrize(
    "cert_type, scope_site_id",
    product([CertificateType.AGGREGATOR_CERTIFICATE, CertificateType.DEVICE_CERTIFICATE], [123, None]),
)
async def test_fetch_mirror_usage_point(
    mock_MirrorUsagePointMapper: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    cert_type: CertificateType,
    scope_site_id: Optional[int],
):
    """Check that the manager will handle interacting with the DB and its responses (agg cert scope)"""

    # Arrange
    mock_session = create_mock_session()
    srt_id = 3
    mapped_mup: MirrorUsagePoint = generate_class_instance(MirrorUsagePoint)
    existing_srt: SiteReadingType = generate_class_instance(SiteReadingType)
    existing_srt.site = generate_class_instance(Site)
    scope: MUPRequestScope = generate_class_instance(MUPRequestScope, source=cert_type, site_id=scope_site_id)

    mock_fetch_site_reading_type_for_aggregator.return_value = existing_srt
    mock_MirrorUsagePointMapper.map_to_response = mock.Mock(return_value=mapped_mup)

    # Act
    result = await MirrorMeteringManager.fetch_mirror_usage_point(mock_session, scope, srt_id)

    # Assert
    assert result is mapped_mup
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        site_reading_type_id=srt_id,
        include_site_relation=True,
    )
    mock_MirrorUsagePointMapper.map_to_response.assert_called_once_with(scope, existing_srt, existing_srt.site)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=None),
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=123),
        generate_class_instance(MUPRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE, site_id=123),
    ],
)
async def test_fetch_mirror_usage_point_no_srt(
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock, scope: MUPRequestScope
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    mock_session = create_mock_session()
    srt_id = 3

    mock_fetch_site_reading_type_for_aggregator.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await MirrorMeteringManager.fetch_mirror_usage_point(mock_session, scope, srt_id)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        site_reading_type_id=srt_id,
        include_site_relation=True,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("return_value, site_id", product([True, False], [99987, None]))
@mock.patch("envoy.server.manager.metering.delete_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.utc_now")
@mock.patch("envoy.server.manager.metering.NotificationManager")
async def test_delete_mirror_usage_point(
    mock_NotificationManager: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
    mock_delete_site_reading_type_for_aggregator: mock.MagicMock,
    return_value: bool,
    site_id: Optional[int],
):
    """Check that the manager will handle interacting with the crud layer / managing the session transaction"""

    # Arrange
    mock_session = create_mock_session()
    scope: MUPRequestScope = generate_class_instance(MUPRequestScope, site_id=site_id)
    delete_time = datetime(2021, 5, 6, 7, 8, 9)
    srt_id = 151512
    mock_NotificationManager.notify_changed_deleted_entities = mock.Mock(return_value=create_async_result(True))

    # Just do a simple passthrough
    mock_utc_now.return_value = delete_time
    mock_delete_site_reading_type_for_aggregator.return_value = return_value

    # Act
    result = await MirrorMeteringManager.delete_mirror_usage_point(mock_session, scope, srt_id)

    # Assert
    assert result == return_value
    assert_mock_session(mock_session, committed=True)  # The session WILL be committed
    mock_delete_site_reading_type_for_aggregator.assert_called_once_with(
        mock_session,
        site_id=scope.site_id,
        site_reading_type_id=srt_id,
        aggregator_id=scope.aggregator_id,
        deleted_time=delete_time,
    )
    mock_utc_now.assert_called_once()
    mock_NotificationManager.notify_changed_deleted_entities.assert_called_once_with(
        SubscriptionResource.READING, delete_time
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.metering.upsert_site_readings")
@mock.patch("envoy.server.manager.metering.MirrorMeterReadingMapper")
@mock.patch("envoy.server.manager.metering.utc_now")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=None),
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=123),
        generate_class_instance(MUPRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE, site_id=123),
    ],
)
async def test_add_or_update_readings(
    mock_utc_now: mock.MagicMock,
    mock_MirrorMeterReadingMapper: mock.MagicMock,
    mock_upsert_site_readings: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    scope: MUPRequestScope,
):
    """Check that the manager will handle interacting with the DB and its responses"""

    # Arrange
    now = datetime(2022, 11, 10, 1, 2, 3)
    mock_utc_now.return_value = now
    mock_session = create_mock_session()
    site_reading_type_id = 3
    mmr: MirrorMeterReading = generate_class_instance(MirrorMeterReading, seed=101)
    existing_sr: SiteReadingType = generate_class_instance(SiteReadingType, seed=202)
    mapped_readings: list[SiteReading] = [generate_class_instance(SiteReading, seed=303)]

    mock_fetch_site_reading_type_for_aggregator.return_value = existing_sr
    mock_MirrorMeterReadingMapper.map_from_request = mock.Mock(return_value=mapped_readings)

    # Act
    await MirrorMeteringManager.add_or_update_readings(mock_session, scope, site_reading_type_id, mmr)

    # Assert
    assert_mock_session(mock_session, committed=True)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        site_reading_type_id=site_reading_type_id,
        include_site_relation=False,
    )
    mock_upsert_site_readings.assert_called_once_with(mock_session, now, mapped_readings)

    mock_MirrorMeterReadingMapper.map_from_request.assert_called_once()
    mapper_call_args = mock_MirrorMeterReadingMapper.map_from_request.call_args_list[0]
    assert mapper_call_args.kwargs["aggregator_id"] == scope.aggregator_id
    assert mapper_call_args.kwargs["site_reading_type_id"] == site_reading_type_id
    assert mapper_call_args.kwargs["changed_time"] == now


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_type_for_aggregator")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=None),
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=123),
        generate_class_instance(MUPRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE, site_id=123),
    ],
)
async def test_add_or_update_readings_no_srt(
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock, scope: MUPRequestScope
):
    """Check that the manager will handle the case where the site reading type DNE"""

    # Arrange
    mock_session = create_mock_session()
    site_reading_type_id = 3
    mmr: MirrorMeterReading = generate_class_instance(MirrorMeterReading, seed=101)

    mock_fetch_site_reading_type_for_aggregator.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await MirrorMeteringManager.add_or_update_readings(mock_session, scope, site_reading_type_id, mmr)

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        session=mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        site_reading_type_id=site_reading_type_id,
        include_site_relation=False,
    )


@pytest.mark.anyio
@mock.patch("envoy.server.manager.metering.fetch_site_reading_types_page_for_aggregator")
@mock.patch("envoy.server.manager.metering.count_site_reading_types_for_aggregator")
@mock.patch("envoy.server.manager.metering.MirrorUsagePointListMapper")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=None),
        generate_class_instance(MUPRequestScope, source=CertificateType.DEVICE_CERTIFICATE, site_id=123),
        generate_class_instance(MUPRequestScope, source=CertificateType.AGGREGATOR_CERTIFICATE, site_id=123),
    ],
)
async def test_list_mirror_usage_points(
    mock_MirrorUsagePointListMapper: mock.MagicMock,
    mock_count_site_reading_types_for_aggregator: mock.MagicMock,
    mock_fetch_site_reading_types_page_for_aggregator: mock.MagicMock,
    scope: MUPRequestScope,
):
    """Check that the manager will handle interacting with the DB and its responses (agg cert)"""

    # Arrange
    mock_session = create_mock_session()
    count = 456
    start = 4
    limit = 5
    changed_after = datetime.now()
    existing_srts: list[SiteReadingType] = [generate_class_instance(SiteReadingType, seed=101)]
    mup_response: list[SiteReading] = [generate_class_instance(SiteReading, seed=202)]

    mock_count_site_reading_types_for_aggregator.return_value = count
    mock_fetch_site_reading_types_page_for_aggregator.return_value = existing_srts
    mock_MirrorUsagePointListMapper.map_to_list_response = mock.Mock(return_value=mup_response)

    # Act
    result = await MirrorMeteringManager.list_mirror_usage_points(mock_session, scope, start, limit, changed_after)
    assert result is mup_response

    # Assert
    assert_mock_session(mock_session, committed=False)
    mock_fetch_site_reading_types_page_for_aggregator.assert_called_once_with(
        session=mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        start=start,
        limit=limit,
        changed_after=changed_after,
    )
    mock_count_site_reading_types_for_aggregator.assert_called_once_with(
        session=mock_session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, changed_after=changed_after
    )

    mock_MirrorUsagePointListMapper.map_to_list_response.assert_called_once_with(scope, existing_srts, count)
