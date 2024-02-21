import unittest.mock as mock
from datetime import datetime
from typing import Optional

import pytest
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionListResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.manager.subscription import SubscriptionManager
from envoy.server.model.subscription import Subscription
from envoy.server.request_state import RequestStateParameters
from tests.data.fake.generator import generate_class_instance
from tests.unit.mocks import assert_mock_session, create_async_result, create_mock_session


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id_filter, scoped_site_id, expect_none",
    [(1, 2, True), (1, 1, False), (1, None, True), (None, 2, False), (None, None, False)],
)
@mock.patch("envoy.server.manager.subscription.select_subscription_by_id")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
async def test_fetch_subscription_by_id_filtering(
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_subscription_by_id: mock.MagicMock,
    site_id_filter: Optional[int],
    scoped_site_id: Optional[int],
    expect_none: bool,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions. It attempts
    to enumerate all the various ways None can be returned (despite getting a sub returned from the DB)"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    sub_id = 87

    mock_sub: Subscription = generate_class_instance(Subscription)
    mock_sub.scoped_site_id = scoped_site_id
    mock_result: Sep2Subscription = generate_class_instance(Sep2Subscription)
    mock_select_subscription_by_id.return_value = mock_sub
    mock_SubscriptionMapper.map_to_response = mock.Mock(return_value=mock_result)

    # Act
    actual_result = await SubscriptionManager.fetch_subscription_by_id(mock_session, rs_params, sub_id, site_id_filter)

    # Assert
    if expect_none:
        assert actual_result is None
    else:
        assert actual_result is mock_result
        mock_SubscriptionMapper.map_to_response.assert_called_once_with(mock_sub, rs_params)

    mock_select_subscription_by_id.assert_called_once_with(
        mock_session, aggregator_id=rs_params.aggregator_id, subscription_id=sub_id
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
    rs_params = RequestStateParameters(981, None)
    sub_id = 87
    mock_select_subscription_by_id.return_value = None

    # Act
    actual_result = await SubscriptionManager.fetch_subscription_by_id(mock_session, rs_params, sub_id, None)

    # Assert
    assert actual_result is None
    mock_select_subscription_by_id.assert_called_once_with(
        mock_session, aggregator_id=rs_params.aggregator_id, subscription_id=sub_id
    )
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.select_subscriptions_for_site")
@mock.patch("envoy.server.manager.subscription.count_subscriptions_for_site")
@mock.patch("envoy.server.manager.subscription.SubscriptionListMapper")
async def test_fetch_subscriptions_for_site(
    mock_SubscriptionListMapper: mock.MagicMock,
    mock_count_subscriptions_for_site: mock.MagicMock,
    mock_select_subscriptions_for_site: mock.MagicMock,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    mock_sub_count = 123
    mock_sub_list = [
        generate_class_instance(Subscription, seed=1, optional_is_none=False),
        generate_class_instance(Subscription, seed=2, optional_is_none=True),
    ]
    site_id = 456
    start = 789
    limit = 101112
    after = datetime(2022, 3, 4, 1, 2, 3)
    mock_result = generate_class_instance(SubscriptionListResponse)

    mock_count_subscriptions_for_site.return_value = mock_sub_count
    mock_select_subscriptions_for_site.return_value = mock_sub_list
    mock_SubscriptionListMapper.map_to_site_response = mock.Mock(return_value=mock_result)

    # Act
    actual_result = await SubscriptionManager.fetch_subscriptions_for_site(
        mock_session, rs_params, site_id, start, after, limit
    )

    # Assert
    assert actual_result is mock_result

    mock_SubscriptionListMapper.map_to_site_response.assert_called_once_with(
        rs_params=rs_params, site_id=site_id, sub_list=mock_sub_list, sub_count=mock_sub_count
    )

    mock_count_subscriptions_for_site.assert_called_once_with(
        mock_session,
        aggregator_id=rs_params.aggregator_id,
        site_id=site_id,
        changed_after=after,
    )
    mock_select_subscriptions_for_site.assert_called_once_with(
        mock_session,
        aggregator_id=rs_params.aggregator_id,
        site_id=site_id,
        start=start,
        changed_after=after,
        limit=limit,
    )
    assert_mock_session(mock_session, committed=False)
