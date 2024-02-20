from datetime import datetime, timezone
from typing import Optional

import pytest

from envoy.server.crud.subscription import (
    count_subscriptions_for_aggregator,
    count_subscriptions_for_site,
    select_subscription_by_id,
    select_subscriptions_for_aggregator,
    select_subscriptions_for_site,
)
from envoy.server.model.subscription import Subscription, SubscriptionResource
from tests.assert_time import assert_datetime_equal
from tests.assert_type import assert_list_type
from tests.postgres_testing import generate_async_session


@pytest.mark.parametrize(
    "aggregator_id, sub_id, expected_sub_id, expected_condition_count",
    [
        # Test the basic config is there and accessible
        (1, 1, 1, 0),
        (1, 2, 2, 0),
        (2, 3, 3, 0),
        (1, 4, 4, 0),
        (1, 5, 5, 2),
        # Test aggregator filters
        (1, 3, None, None),
        (2, 1, None, None),
        (99, 1, None, None),
        # Test ID filters
        (1, 99, None, None),
    ],
)
@pytest.mark.anyio
async def test_select_subscription_by_id_filters(
    pg_base_config,
    aggregator_id: int,
    sub_id: int,
    expected_sub_id: Optional[int],
    expected_condition_count: Optional[int],
):
    """Validates select_subscription_by_id filters correctly for some expected values"""
    async with generate_async_session(pg_base_config) as session:

        sub = await select_subscription_by_id(session, aggregator_id, sub_id)
        if sub is None:
            assert expected_sub_id is None
            assert expected_condition_count is None
        else:
            assert isinstance(sub, Subscription)
            assert sub.subscription_id == expected_sub_id
            assert len(sub.conditions) == expected_condition_count


@pytest.mark.anyio
async def test_select_subscription_by_id_content(pg_base_config):
    """Validates select_subscription_by_id filters correctly for some expected values"""
    async with generate_async_session(pg_base_config) as session:

        sub_5 = await select_subscription_by_id(session, 1, 5)
        assert isinstance(sub_5, Subscription)

        assert sub_5.subscription_id == 5
        assert sub_5.aggregator_id == 1
        assert_datetime_equal(sub_5.changed_time, datetime(2024, 1, 2, 15, 22, 33, 500000, tzinfo=timezone.utc))
        assert sub_5.resource_type == SubscriptionResource.READING
        assert sub_5.scoped_site_id is None
        assert sub_5.resource_id is None
        assert sub_5.entity_limit == 55
        assert sub_5.notification_uri == "https://example.com:55/path/"
        assert len(sub_5.conditions) == 2
        assert sub_5.conditions[0].lower_threshold == 1
        assert sub_5.conditions[0].upper_threshold == 11
        assert sub_5.conditions[1].lower_threshold == 2
        assert sub_5.conditions[1].upper_threshold == 12


@pytest.mark.parametrize(
    "aggregator_id, start, limit, changed_after, expected_sub_ids",
    [
        # Test the basic config is there and accessible
        (1, 0, None, datetime.min, [1, 2, 4, 5]),
        # Test basic pagination
        (1, 0, 2, datetime.min, [1, 2]),
        (1, 2, None, datetime.min, [4, 5]),
        (1, 2, 1, datetime.min, [4]),
        (1, 5, None, datetime.min, []),
        (1, 99, None, datetime.min, []),
        (1, 0, 99, datetime.min, [1, 2, 4, 5]),
        # Test datetime filter
        (1, 0, None, datetime(2024, 1, 2, 12, 20, 0, tzinfo=timezone.utc), [2, 4, 5]),
        (1, 0, None, datetime(2024, 1, 2, 15, 22, 33, tzinfo=timezone.utc), [5]),
        (1, 0, None, datetime(2024, 1, 2, 15, 22, 34, tzinfo=timezone.utc), []),
        (1, 1, 1, datetime(2024, 1, 2, 12, 20, 0, tzinfo=timezone.utc), [4]),
        # Test aggregator filters
        (2, 0, None, datetime.min, [3]),
        (3, 0, None, datetime.min, []),
        (-1, 0, None, datetime.min, []),
    ],
)
@pytest.mark.anyio
async def test_select_count_subscriptions_for_aggregator(
    pg_base_config,
    aggregator_id: int,
    start: int,
    limit: Optional[int],
    changed_after: datetime,
    expected_sub_ids: list[int],
):
    """Simple tests to ensure the select/counts work for various filters"""
    async with generate_async_session(pg_base_config) as session:

        subs = await select_subscriptions_for_aggregator(session, aggregator_id, start, changed_after, limit)
        assert_list_type(Subscription, subs, len(expected_sub_ids))
        assert all([len(s.conditions) >= 0 for s in subs])
        assert all([s.aggregator_id == aggregator_id for s in subs])
        assert [s.subscription_id for s in subs] == expected_sub_ids

        count = await count_subscriptions_for_aggregator(session, aggregator_id, changed_after)

        # Slightly complex way of ensuring our count matches our returned items
        # (but in a way that accounts for pagination)
        limit_or_max = 99999 if limit is None else limit
        start_bounded_to_count = min(start, 4)
        assert min(count, limit_or_max) == min(len(expected_sub_ids) + start_bounded_to_count, limit_or_max)


@pytest.mark.anyio
async def test_select_subscriptions_for_aggregator_content_only(pg_base_config):
    """Checks that the Subs are populated correct with select_subscriptions_for_aggregator"""
    async with generate_async_session(pg_base_config) as session:
        # Select our subscription of interest to inspect
        subs = await select_subscriptions_for_aggregator(session, 1, 2, datetime.min, None)
        assert_list_type(Subscription, subs, 2)

        sub_4 = subs[0]
        assert sub_4.subscription_id == 4
        assert sub_4.aggregator_id == 1
        assert_datetime_equal(sub_4.changed_time, datetime(2024, 1, 2, 14, 22, 33, 500000, tzinfo=timezone.utc))
        assert sub_4.resource_type == SubscriptionResource.SITE
        assert sub_4.scoped_site_id == 4
        assert sub_4.resource_id == 4
        assert sub_4.entity_limit == 44
        assert sub_4.notification_uri == "https://example.com:44/path/"
        assert len(sub_4.conditions) == 0

        sub_5 = subs[1]
        assert sub_5.subscription_id == 5
        assert sub_5.aggregator_id == 1
        assert_datetime_equal(sub_5.changed_time, datetime(2024, 1, 2, 15, 22, 33, 500000, tzinfo=timezone.utc))
        assert sub_5.resource_type == SubscriptionResource.READING
        assert sub_5.scoped_site_id is None
        assert sub_5.resource_id is None
        assert sub_5.entity_limit == 55
        assert sub_5.notification_uri == "https://example.com:55/path/"
        assert len(sub_5.conditions) == 2
        assert sub_5.conditions[0].lower_threshold == 1
        assert sub_5.conditions[0].upper_threshold == 11
        assert sub_5.conditions[1].lower_threshold == 2
        assert sub_5.conditions[1].upper_threshold == 12


@pytest.mark.parametrize(
    "aggregator_id, site_id, start, limit, changed_after, expected_sub_ids",
    [
        # Test the basic config is there and accessible
        (1, 1, 0, None, datetime.min, []),
        (1, 2, 0, None, datetime.min, [2]),
        (2, 3, 0, None, datetime.min, [3]),
        (1, 4, 0, None, datetime.min, [4, 5]),
        (1, 5, 0, None, datetime.min, []),
        # Test basic pagination
        (1, 4, 0, 1, datetime.min, [4]),
        (1, 4, 1, 1, datetime.min, [5]),
        (1, 4, 1, None, datetime.min, [5]),
        # Test datetime filter
        (1, 4, 0, None, datetime(2024, 1, 2, 12, 20, 0, tzinfo=timezone.utc), [4, 5]),
        (1, 4, 0, None, datetime(2024, 1, 2, 15, 22, 33, tzinfo=timezone.utc), [5]),
        (1, 4, 0, None, datetime(2024, 1, 2, 15, 22, 34, tzinfo=timezone.utc), []),
        # Test aggregator filters
        (2, 4, 0, None, datetime.min, []),
        (-1, 4, 0, None, datetime.min, []),
        (1, 3, 0, None, datetime.min, []),
    ],
)
@pytest.mark.anyio
async def test_select_count_subscriptions_for_site(
    pg_base_config,
    aggregator_id: int,
    site_id: int,
    start: int,
    limit: Optional[int],
    changed_after: datetime,
    expected_sub_ids: list[int],
):
    """Simple tests to ensure the select/counts work for various filters"""

    # Start by updating our subscription 5 to appear under site 4 (to ensure we get multiple in a list)
    async with generate_async_session(pg_base_config) as session:
        sub_5 = await select_subscription_by_id(session, 1, 5)
        sub_5.scoped_site_id = 4
        await session.commit()

    async with generate_async_session(pg_base_config) as session:

        subs = await select_subscriptions_for_site(session, aggregator_id, site_id, start, changed_after, limit)
        assert_list_type(Subscription, subs, len(expected_sub_ids))
        assert all([len(s.conditions) >= 0 for s in subs])
        assert all([s.aggregator_id == aggregator_id for s in subs])
        assert [s.subscription_id for s in subs] == expected_sub_ids

        count = await count_subscriptions_for_site(session, aggregator_id, site_id, changed_after)

        # Slightly complex way of ensuring our count matches our returned items
        # (but in a way that accounts for pagination)
        limit_or_max = 99999 if limit is None else limit
        start_bounded_to_count = min(start, 2)
        assert min(count, limit_or_max) == min(len(expected_sub_ids) + start_bounded_to_count, limit_or_max)


@pytest.mark.anyio
async def test_select_subscriptions_for_site_content_only(pg_base_config):
    """Checks that the Subs are populated correct with select_subscriptions_for_aggregator"""

    # Start by updating our subscription 5 to appear under site 4 (to ensure we get multiple in a list)
    async with generate_async_session(pg_base_config) as session:
        sub_5 = await select_subscription_by_id(session, 1, 5)
        sub_5.scoped_site_id = 4
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Select our subscription of interest to inspect
        subs = await select_subscriptions_for_site(session, 1, 4, 0, datetime.min, None)
        assert_list_type(Subscription, subs, 2)

        sub_4 = subs[0]
        assert sub_4.subscription_id == 4
        assert sub_4.aggregator_id == 1
        assert_datetime_equal(sub_4.changed_time, datetime(2024, 1, 2, 14, 22, 33, 500000, tzinfo=timezone.utc))
        assert sub_4.resource_type == SubscriptionResource.SITE
        assert sub_4.scoped_site_id == 4
        assert sub_4.resource_id == 4
        assert sub_4.entity_limit == 44
        assert sub_4.notification_uri == "https://example.com:44/path/"
        assert len(sub_4.conditions) == 0

        sub_5 = subs[1]
        assert sub_5.subscription_id == 5
        assert sub_5.aggregator_id == 1
        assert_datetime_equal(sub_5.changed_time, datetime(2024, 1, 2, 15, 22, 33, 500000, tzinfo=timezone.utc))
        assert sub_5.resource_type == SubscriptionResource.READING
        assert sub_5.scoped_site_id == 4
        assert sub_5.resource_id is None
        assert sub_5.entity_limit == 55
        assert sub_5.notification_uri == "https://example.com:55/path/"
        assert len(sub_5.conditions) == 2
        assert sub_5.conditions[0].lower_threshold == 1
        assert sub_5.conditions[0].upper_threshold == 11
        assert sub_5.conditions[1].lower_threshold == 2
        assert sub_5.conditions[1].upper_threshold == 12
