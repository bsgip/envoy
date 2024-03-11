import unittest.mock as mock
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from envoy_schema.server.schema.sep2.der import (
    DERAvailability,
    DERCapability,
    DERControlType,
    DERListResponse,
    DERSettings,
    DERStatus,
)
from sqlalchemy import func, select

from envoy.server.crud.der import generate_default_site_der, select_site_der_for_site
from envoy.server.exception import NotFoundError
from envoy.server.manager.der import PUBLIC_SITE_DER_ID, DERCapabilityManager, DERManager, site_der_for_site
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID
from envoy.server.mapper.sep2.der import DERCapabilityMapper, to_hex_binary
from envoy.server.model.site import Site, SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.request_state import RequestStateParameters
from tests.assert_time import assert_datetime_equal
from tests.data.fake.generator import assert_class_instance_equality, clone_class_instance, generate_class_instance
from tests.postgres_testing import generate_async_session
from tests.unit.mocks import assert_mock_session, create_mock_session


@mock.patch("envoy.server.manager.der.select_site_der_for_site")
@mock.patch("envoy.server.manager.der.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.der.generate_default_site_der")
@pytest.mark.anyio
async def test_site_der_for_site_no_der(
    mock_generate_default_site_der: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_select_site_der_for_site: mock.MagicMock,
):
    """Fetch when no existing SiteDER exists"""
    site_id = 123
    agg_id = 456
    mock_session = create_mock_session()

    site_der: SiteDER = generate_class_instance(SiteDER)
    site: Site = generate_class_instance(Site)
    mock_select_site_der_for_site.return_value = None
    mock_select_single_site_with_site_id.return_value = site
    mock_generate_default_site_der.return_value = site_der

    result = await site_der_for_site(mock_session, agg_id, site_id)
    assert result is site_der

    mock_select_site_der_for_site.assert_called_once_with(mock_session, site_id=site_id, aggregator_id=agg_id)
    mock_select_single_site_with_site_id.assert_called_with(mock_session, site_id=site_id, aggregator_id=agg_id)
    mock_generate_default_site_der.assert_called_with(site_id=site_id, changed_time=site.changed_time)
    assert_mock_session(mock_session)


@mock.patch("envoy.server.manager.der.select_site_der_for_site")
@mock.patch("envoy.server.manager.der.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.der.generate_default_site_der")
@pytest.mark.anyio
async def test_site_der_for_site_existing_der(
    mock_generate_default_site_der: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_select_site_der_for_site: mock.MagicMock,
):
    """Fetch when SiteDER already exists"""
    site_id = 123
    agg_id = 456
    mock_session = create_mock_session()

    site_der: SiteDER = generate_class_instance(SiteDER)
    mock_select_site_der_for_site.return_value = site_der

    result = await site_der_for_site(mock_session, agg_id, site_id)
    assert result is site_der

    mock_select_site_der_for_site.assert_called_once_with(mock_session, site_id=site_id, aggregator_id=agg_id)
    mock_select_single_site_with_site_id.assert_not_called()
    mock_generate_default_site_der.assert_not_called()
    assert_mock_session(mock_session)


@mock.patch("envoy.server.manager.der.select_site_der_for_site")
@mock.patch("envoy.server.manager.der.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.der.generate_default_site_der")
@pytest.mark.anyio
async def test_site_der_for_site_inaccessible_site(
    mock_generate_default_site_der: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_select_site_der_for_site: mock.MagicMock,
):
    """Fetch when SiteDER doesn't exist and the site isn't accessible"""
    site_id = 123
    agg_id = 456
    mock_session = create_mock_session()

    mock_select_site_der_for_site.return_value = None
    mock_select_single_site_with_site_id.return_value = None

    with pytest.raises(NotFoundError):
        await site_der_for_site(mock_session, agg_id, site_id)

    mock_select_site_der_for_site.assert_called_once_with(mock_session, site_id=site_id, aggregator_id=agg_id)
    mock_select_single_site_with_site_id.assert_called_with(mock_session, site_id=site_id, aggregator_id=agg_id)
    mock_generate_default_site_der.assert_not_called()
    assert_mock_session(mock_session)


@mock.patch("envoy.server.manager.der.DERMapper")
@mock.patch("envoy.server.manager.der.site_der_for_site")
@pytest.mark.anyio
async def test_fetch_der_for_site_der_exists(
    mock_site_der_for_site: mock.MagicMock,
    mock_DERMapper: mock.MagicMock,
):
    """Fetch when site_der_for_site returns an instance"""
    site_id = 123
    rs_params = RequestStateParameters(456, None)
    mock_session = create_mock_session()

    site_der: SiteDER = generate_class_instance(SiteDER, seed=101)
    mock_site_der_for_site.return_value = site_der
    mock_map = mock.Mock()
    mock_DERMapper.map_to_response = mock.Mock(return_value=mock_map)

    result = await DERManager.fetch_der_for_site(mock_session, site_id, PUBLIC_SITE_DER_ID, rs_params)
    assert result is mock_map

    assert site_der.site_der_id == PUBLIC_SITE_DER_ID, "This should've been set during the fetch"
    mock_DERMapper.map_to_response.assert_called_once_with(rs_params, site_der, DOE_PROGRAM_ID)
    mock_site_der_for_site.assert_called_once_with(mock_session, aggregator_id=rs_params.aggregator_id, site_id=site_id)
    assert_mock_session(mock_session)


@mock.patch("envoy.server.manager.der.DERMapper")
@mock.patch("envoy.server.manager.der.site_der_for_site")
@pytest.mark.anyio
async def test_fetch_der_for_site_bad_der_id(
    mock_site_der_for_site: mock.MagicMock,
    mock_DERMapper: mock.MagicMock,
):
    """Fetch when DER ID is incorrect"""
    site_id = 123
    rs_params = RequestStateParameters(456, None)
    mock_session = create_mock_session()

    with pytest.raises(NotFoundError):
        await DERManager.fetch_der_for_site(mock_session, site_id, PUBLIC_SITE_DER_ID + 1, rs_params)

    mock_DERMapper.assert_not_called()
    mock_site_der_for_site.assert_not_called()
    assert_mock_session(mock_session)


AFTER_EPOCH = datetime(2022, 10, 9, 8, 7, 6, tzinfo=timezone.utc)


@mock.patch("envoy.server.manager.der.site_der_for_site")
@pytest.mark.parametrize(
    "start, limit, after, expected_count",
    [
        (0, 99, AFTER_EPOCH - timedelta(seconds=10), 1),
        (0, 0, AFTER_EPOCH - timedelta(seconds=10), 0),
        (1, 99, AFTER_EPOCH - timedelta(seconds=10), 0),
        (0, 99, AFTER_EPOCH + timedelta(seconds=10), 0),
    ],
)
@pytest.mark.anyio
async def test_fetch_der_list_for_site_pagination(
    mock_site_der_for_site: mock.MagicMock, start: int, limit: int, after: datetime, expected_count: int
):
    """Fetch when site_der_for_site returns an instance"""
    site_id = 123
    rs_params = RequestStateParameters(456, None)
    mock_session = create_mock_session()

    site_der: SiteDER = generate_class_instance(SiteDER, seed=101)
    site_der.changed_time = AFTER_EPOCH
    mock_site_der_for_site.return_value = site_der

    result = await DERManager.fetch_der_list_for_site(mock_session, site_id, rs_params, start, limit, after)
    assert isinstance(result, DERListResponse)

    assert len(result.DER_) == expected_count
    mock_site_der_for_site.assert_called_once_with(mock_session, aggregator_id=rs_params.aggregator_id, site_id=site_id)
    assert_mock_session(mock_session)


@pytest.mark.parametrize(
    "agg_id, site_id, der_id",
    [
        (99, 1, PUBLIC_SITE_DER_ID),  # invalid agg_id
        (2, 1, PUBLIC_SITE_DER_ID),  # Invalid agg_id
        (1, 99, PUBLIC_SITE_DER_ID),  # Invalid site id
        (1, 1, PUBLIC_SITE_DER_ID + 1),  # invalid DER id
    ],
)
@pytest.mark.anyio
async def test_upsert_der_capability_not_found(pg_base_config, agg_id: int, site_id: int, der_id: int):
    """Tests the various ways a NotFoundError can be raised"""
    rs_params = RequestStateParameters(agg_id, None)

    async with generate_async_session(pg_base_config) as session:
        e: DERCapability = generate_class_instance(DERCapability, generate_relationships=True)
        e.modesSupported = to_hex_binary(DERControlType.OP_MOD_CONNECT)

        with pytest.raises(NotFoundError):
            await DERCapabilityManager.upsert_der_capability_for_site(
                session,
                site_id,
                der_id,
                rs_params,
                e,
            )

    # Validate we haven't added any rows on accident
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(func.count()).select_from(SiteDERRating))
        assert resp.scalar_one() == 0


@pytest.mark.parametrize(
    "agg_id, site_id, der_id",
    [
        (99, 1, PUBLIC_SITE_DER_ID),  # invalid agg_id
        (2, 1, PUBLIC_SITE_DER_ID),  # Invalid agg_id
        (1, 99, PUBLIC_SITE_DER_ID),  # Invalid site id
        (1, 1, PUBLIC_SITE_DER_ID + 1),  # invalid DER id
        (1, 1, PUBLIC_SITE_DER_ID),  # There is no entity record in the db
        (1, 4, PUBLIC_SITE_DER_ID),  # There is DER or entity record in the db
    ],
)
@pytest.mark.anyio
async def test_fetch_der_capability_not_found(pg_base_config, agg_id: int, site_id: int, der_id: int):
    """Tests the various ways a NotFoundError can be raised"""
    rs_params = RequestStateParameters(agg_id, None)

    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(NotFoundError):
            await DERCapabilityManager.fetch_der_capability_for_site(
                session,
                site_id,
                der_id,
                rs_params,
            )


@pytest.mark.parametrize(
    "site_id, update_site_der_id",
    [
        (1, None),  # Existing DER - insert record
        (1, 2),  # Existing DER - update record
        (4, None),  # Missing DER - insert both
    ],
)
@pytest.mark.anyio
async def test_upsert_der_capability_roundtrip(pg_base_config, site_id: int, update_site_der_id: Optional[int]):
    """Tests the various success paths through updating"""
    agg_id = 1
    rs_params = RequestStateParameters(agg_id, "/custom/prefix")

    # If set - insert a new entity that will be forced to update
    if update_site_der_id is not None:
        async with generate_async_session(pg_base_config) as session:
            updated_entity: SiteDERRating = generate_class_instance(SiteDERRating, seed=1001)
            updated_entity.site_der_id = update_site_der_id
            session.add(updated_entity)
            await session.commit()

    # Do the upsert
    expected: DERCapability = generate_class_instance(DERCapability, seed=22, generate_relationships=True)
    expected.modesSupported = to_hex_binary(
        DERControlType.OP_MOD_HVRT_MUST_TRIP | DERControlType.OP_MOD_HVRT_MOMENTARY_CESSATION
    )
    async with generate_async_session(pg_base_config) as session:
        await DERCapabilityManager.upsert_der_capability_for_site(
            session,
            site_id,
            PUBLIC_SITE_DER_ID,
            rs_params,
            clone_class_instance(expected),
        )

    # Use a new session to query everything back
    async with generate_async_session(pg_base_config) as session:
        actual = await DERCapabilityManager.fetch_der_capability_for_site(
            session, site_id, PUBLIC_SITE_DER_ID, rs_params
        )

        assert_class_instance_equality(
            DERCapability,
            expected,
            actual,
            ignored_properties=set(["href", "subscribable", "type"]),
        )
        assert actual.href.startswith(rs_params.href_prefix)
        assert str(site_id) in actual.href

    # Validate we haven't added multiple rows on accident
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(func.count()).select_from(SiteDERRating))
        assert resp.scalar_one() == 1
