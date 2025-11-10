import unittest.mock as mock
from datetime import datetime
from typing import Optional

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionListResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.manager.subscription import SubscriptionManager
from envoy.server.model.aggregator import Aggregator, AggregatorDomain
from envoy.server.model.doe import SiteControlGroup
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import Tariff
from envoy.server.request_scope import AggregatorRequestScope


@pytest.mark.anyio
@pytest.mark.parametrize(
    "scoped_site_id, sub_site_id, expect_none",
    [
        (111, 222, True),
        (111, 111, False),
        (111, None, True),
        (None, 222, False),
        (None, None, False),
    ],
)
@mock.patch("envoy.server.manager.subscription.select_subscription_by_id")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
async def test_fetch_subscription_by_id_filtering(
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_subscription_by_id: mock.MagicMock,
    scoped_site_id: Optional[int],
    sub_site_id: Optional[int],
    expect_none: bool,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions. It attempts
    to enumerate all the various ways None can be returned (despite getting a sub returned from the DB)"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope, site_id=scoped_site_id)
    sub_id = 87

    mock_sub: Subscription = generate_class_instance(Subscription, scoped_site_id=sub_site_id)
    mock_result: Sep2Subscription = generate_class_instance(Sep2Subscription)
    mock_select_subscription_by_id.return_value = mock_sub
    mock_SubscriptionMapper.map_to_response = mock.Mock(return_value=mock_result)

    # Act
    actual_result = await SubscriptionManager.fetch_subscription_by_id(mock_session, scope, sub_id)

    # Assert
    if expect_none:
        assert actual_result is None
    else:
        assert actual_result is mock_result
        mock_SubscriptionMapper.map_to_response.assert_called_once_with(mock_sub, scope)

    mock_select_subscription_by_id.assert_called_once_with(
        mock_session, aggregator_id=scope.aggregator_id, subscription_id=sub_id
    )
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.select_subscription_by_id")
async def test_fetch_subscription_by_id_not_found(
    mock_select_subscription_by_id: mock.MagicMock,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope, site_id=None)
    sub_id = 87
    mock_select_subscription_by_id.return_value = None

    # Act
    actual_result = await SubscriptionManager.fetch_subscription_by_id(mock_session, scope, sub_id)

    # Assert
    assert actual_result is None
    mock_select_subscription_by_id.assert_called_once_with(
        mock_session, aggregator_id=scope.aggregator_id, subscription_id=sub_id
    )
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.select_subscriptions_for_site")
@mock.patch("envoy.server.manager.subscription.count_subscriptions_for_site")
@mock.patch("envoy.server.manager.subscription.SubscriptionListMapper")
@pytest.mark.parametrize(
    "scope",
    [
        generate_class_instance(AggregatorRequestScope, aggregator_id=111, site_id=None),
        generate_class_instance(AggregatorRequestScope, aggregator_id=111, site_id=222),
    ],
)
async def test_fetch_subscriptions_for_site(
    mock_SubscriptionListMapper: mock.MagicMock,
    mock_count_subscriptions_for_site: mock.MagicMock,
    mock_select_subscriptions_for_site: mock.MagicMock,
    scope: AggregatorRequestScope,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    mock_sub_count = 123
    mock_sub_list = [
        generate_class_instance(Subscription, seed=1, optional_is_none=False),
        generate_class_instance(Subscription, seed=2, optional_is_none=True),
    ]
    start = 789
    limit = 101112
    after = datetime(2022, 3, 4, 1, 2, 3)
    mock_result = generate_class_instance(SubscriptionListResponse)

    mock_count_subscriptions_for_site.return_value = mock_sub_count
    mock_select_subscriptions_for_site.return_value = mock_sub_list
    mock_SubscriptionListMapper.map_to_site_response = mock.Mock(return_value=mock_result)

    # Act
    actual_result = await SubscriptionManager.fetch_subscriptions_for_site(mock_session, scope, start, after, limit)

    # Assert
    assert actual_result is mock_result

    mock_SubscriptionListMapper.map_to_site_response.assert_called_once_with(
        scope=scope, sub_list=mock_sub_list, sub_count=mock_sub_count
    )

    mock_count_subscriptions_for_site.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        changed_after=after,
    )
    mock_select_subscriptions_for_site.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        start=start,
        changed_after=after,
        limit=limit,
    )
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "retval, scope_site_id",
    zip([True, False], [111, None]),
)
@mock.patch("envoy.server.manager.subscription.delete_subscription_for_site")
@mock.patch("envoy.server.manager.subscription.utc_now")
async def test_delete_subscription_for_site(
    mock_utc_now: mock.MagicMock,
    mock_delete_subscription_for_site: mock.MagicMock,
    retval: bool,
    scope_site_id: Optional[int],
):
    """Ensures session is handled properly on delete"""
    # Arrange
    deleted_time = datetime(2011, 4, 6)
    mock_utc_now.return_value = deleted_time
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope, site_id=scope_site_id)

    sub_id = 5213

    mock_delete_subscription_for_site.return_value = retval

    # Act
    actual_result = await SubscriptionManager.delete_subscription_for_site(mock_session, scope, sub_id)

    # Assert
    assert actual_result == retval

    mock_delete_subscription_for_site.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        subscription_id=sub_id,
        deleted_time=deleted_time,
    )

    assert_mock_session(mock_session, committed=True)


@pytest.mark.parametrize(
    "scope_site_id, sub_site_id, sub_site_exists, expected_valid",
    [
        (123, 123, True, True),  # Single site subscription
        (123, 124, True, False),  # Wrong site id
        (123, 124, False, False),  # Wrong site id
        (123, None, True, False),  # Can't expand subscription scope beyond
        (None, None, False, True),  # Fully unscoped subscription
        (None, None, True, True),  # Fully unscoped subscription
        (None, 123, False, False),  # Unscoped but the referenced site DNE
        (None, 123, True, True),  # Unscoped and site exists
    ],
)
@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.select_single_site_with_site_id")
async def test_validate_subscription_site_scope(
    mock_select_single_site_with_site_id: mock.MagicMock,
    scope_site_id: Optional[int],
    sub_site_id: Optional[int],
    sub_site_exists: bool,
    expected_valid: bool,
):
    """Tests the various pathways in validate_subscription_site_scope"""
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope, site_id=scope_site_id)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.TARIFF_GENERATED_RATE,
        scoped_site_id=sub_site_id,
    )
    mock_select_single_site_with_site_id.return_value = generate_class_instance(Site) if sub_site_exists else None

    # Act
    if expected_valid:
        await SubscriptionManager.validate_subscription_site_scope(mock_session, scope, mapped_sub)
    else:
        with pytest.raises(BadRequestError):
            await SubscriptionManager.validate_subscription_site_scope(mock_session, scope, mapped_sub)

    assert_mock_session(mock_session, committed=False)


@pytest.mark.parametrize(
    "sub_site_id, resource_id, resource_type, site_control_group, reading_types, tariff, expected_valid",
    [
        (123, 456, SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, None, None, None, False),  # SiteControl DNE
        (None, 456, SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, None, None, None, False),  # SiteControl DNE
        (123, 456, SubscriptionResource.TARIFF_GENERATED_RATE, None, None, None, False),  # Tariff DNE
        (None, 456, SubscriptionResource.TARIFF_GENERATED_RATE, None, None, None, False),  # Tariff DNE
        (123, 456, SubscriptionResource.READING, None, None, None, False),  # Reading Types DNE
        (None, 456, SubscriptionResource.READING, None, None, None, False),  # Reading Types DNE
        (123, 456, SubscriptionResource.READING, None, [], None, False),  # Reading Types DNE
        (123, 456, SubscriptionResource.SITE_DER_AVAILABILITY, None, None, None, False),  # Bad resource ID
        (None, 456, SubscriptionResource.SITE_DER_AVAILABILITY, None, None, None, False),  # Bad resource ID
        (123, 456, SubscriptionResource.SITE_DER_RATING, None, None, None, False),  # Bad resource ID
        (None, 456, SubscriptionResource.SITE_DER_RATING, None, None, None, False),  # Bad resource ID
        (123, 456, SubscriptionResource.SITE_DER_SETTING, None, None, None, False),  # Bad resource ID
        (None, 456, SubscriptionResource.SITE_DER_SETTING, None, None, None, False),  # Bad resource ID
        (123, 456, SubscriptionResource.SITE_DER_STATUS, None, None, None, False),  # Bad resource ID
        (None, 456, SubscriptionResource.SITE_DER_STATUS, None, None, None, False),  # Bad resource ID
        (123, 456, SubscriptionResource.DEFAULT_SITE_CONTROL, None, None, None, False),  # SiteControl DNE
        (None, 456, SubscriptionResource.DEFAULT_SITE_CONTROL, None, None, None, False),  # SiteControl DNE
        (None, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_AVAILABILITY, None, None, None, True),
        (123, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_AVAILABILITY, None, None, None, True),
        (None, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_RATING, None, None, None, True),
        (123, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_RATING, None, None, None, True),
        (None, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_SETTING, None, None, None, True),
        (123, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_SETTING, None, None, None, True),
        (None, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_STATUS, None, None, None, True),
        (123, PUBLIC_SITE_DER_ID, SubscriptionResource.SITE_DER_STATUS, None, None, None, True),
        (
            123,
            456,
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
            generate_class_instance(SiteControlGroup),
            None,
            None,
            True,
        ),
        (
            123,
            456,
            SubscriptionResource.DEFAULT_SITE_CONTROL,
            generate_class_instance(SiteControlGroup),
            None,
            None,
            True,
        ),
        (
            123,
            456,
            SubscriptionResource.SITE_CONTROL_GROUP,
            generate_class_instance(SiteControlGroup),
            None,
            None,
            True,
        ),
        (None, None, None, None, None, None, True),  # No resource id - will validate fine
        (123, None, None, None, None, None, True),  # No resource id - will validate fine
    ],
)
@mock.patch("envoy.server.manager.subscription.select_site_control_group_by_id")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_types_for_group")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@pytest.mark.anyio
async def test_validate_subscription_linked_resource(
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_types_for_group: mock.MagicMock,
    mock_select_site_control_group_by_id: mock.MagicMock,
    sub_site_id: Optional[int],
    resource_id: Optional[int],
    resource_type: SubscriptionResource,
    site_control_group: Optional[SiteControlGroup],
    reading_types: Optional[list[SiteReadingType]],
    tariff: Optional[Tariff],
    expected_valid: bool,
):
    """Tests the various pathways in validate_subscription_linked_resource"""
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope, site_id=sub_site_id)
    mapped_sub = Subscription(resource_type=resource_type, scoped_site_id=sub_site_id, resource_id=resource_id)

    mock_select_site_control_group_by_id.return_value = site_control_group
    mock_fetch_site_reading_types_for_group.return_value = reading_types
    mock_select_single_tariff.return_value = tariff

    if expected_valid:
        await SubscriptionManager.validate_subscription_linked_resource(mock_session, scope, mapped_sub)
    else:
        with pytest.raises(BadRequestError):
            await SubscriptionManager.validate_subscription_linked_resource(mock_session, scope, mapped_sub)

    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper.map_from_request")
@mock.patch("envoy.server.manager.subscription.upsert_subscription")
@mock.patch("envoy.server.manager.subscription.SubscriptionManager.validate_subscription_linked_resource")
@mock.patch("envoy.server.manager.subscription.SubscriptionManager.validate_subscription_site_scope")
async def test_add_subscription_for_site_bad_agg_lookup(
    mock_validate_subscription_site_scope: mock.MagicMock,
    mock_validate_subscription_linked_resource: mock.MagicMock,
    mock_upsert_subscription: mock.MagicMock,
    mock_map_from_request: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope)
    now = datetime(2014, 4, 5, 6, 7, 8)
    sub = generate_class_instance(Sep2Subscription)

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = None
    mock_upsert_subscription.return_value = 98765

    # Act
    with pytest.raises(NotFoundError):
        await SubscriptionManager.add_subscription_for_site(mock_session, scope, sub)

    assert_mock_session(mock_session, committed=False)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, scope.aggregator_id)
    mock_validate_subscription_site_scope.assert_not_called()
    mock_validate_subscription_linked_resource.assert_not_called()
    mock_map_from_request.assert_not_called()
    mock_upsert_subscription.assert_not_called()


@pytest.mark.parametrize("scope_validate_fail", [True, False])
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper.map_from_request")
@mock.patch("envoy.server.manager.subscription.upsert_subscription")
@mock.patch("envoy.server.manager.subscription.SubscriptionManager.validate_subscription_linked_resource")
@mock.patch("envoy.server.manager.subscription.SubscriptionManager.validate_subscription_site_scope")
@pytest.mark.anyio
async def test_add_subscription_for_site_validate_errors(
    mock_validate_subscription_site_scope: mock.MagicMock,
    mock_validate_subscription_linked_resource: mock.MagicMock,
    mock_upsert_subscription: mock.MagicMock,
    mock_map_from_request: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
    scope_validate_fail: bool,
):
    """If any of the validate functions raise an error - it will prevent the creation of the subscription"""
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_reading_type_id = 5432
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.READING, scoped_site_id=scope.site_id + 2, resource_id=site_reading_type_id
    )

    if scope_validate_fail:
        mock_validate_subscription_site_scope.side_effect = BadRequestError("My mock error")
    else:
        mock_validate_subscription_linked_resource.side_effect = BadRequestError("My mock error")

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_map_from_request.return_value = mapped_sub
    mock_upsert_subscription.return_value = 98765

    # Act
    with pytest.raises(BadRequestError):
        await SubscriptionManager.add_subscription_for_site(mock_session, scope, sub)

    assert_mock_session(mock_session, committed=False)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, scope.aggregator_id)
    mock_map_from_request.assert_called_once_with(
        subscription=sub,
        scope=scope,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )

    assert mock_validate_subscription_site_scope.call_count or mock_validate_subscription_linked_resource.call_count
    mock_upsert_subscription.assert_not_called()
    mock_validate_subscription_site_scope.assert_called_once_with(mock_session, scope, mapped_sub)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper.map_from_request")
@mock.patch("envoy.server.manager.subscription.upsert_subscription")
@mock.patch("envoy.server.manager.subscription.SubscriptionManager.validate_subscription_linked_resource")
@mock.patch("envoy.server.manager.subscription.SubscriptionManager.validate_subscription_site_scope")
async def test_add_subscription_for_site(
    mock_validate_subscription_site_scope: mock.MagicMock,
    mock_validate_subscription_linked_resource: mock.MagicMock,
    mock_upsert_subscription: mock.MagicMock,
    mock_map_from_request: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    scope: AggregatorRequestScope = generate_class_instance(AggregatorRequestScope, site_id=None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    tariff_id = 5433
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.TARIFF_GENERATED_RATE, scoped_site_id=123, resource_id=tariff_id
    )

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_map_from_request.return_value = mapped_sub
    mock_upsert_subscription.return_value = 98765

    # Act
    actual_result = await SubscriptionManager.add_subscription_for_site(mock_session, scope, sub)

    assert actual_result == mock_upsert_subscription.return_value
    assert_mock_session(mock_session, committed=True)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, scope.aggregator_id)
    mock_map_from_request.assert_called_once_with(
        subscription=sub,
        scope=scope,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )
    mock_upsert_subscription.assert_called_once_with(mock_session, mapped_sub)

    mock_validate_subscription_site_scope.assert_called_once_with(mock_session, scope, mapped_sub)
    mock_validate_subscription_linked_resource.assert_called_once_with(mock_session, scope, mapped_sub)
