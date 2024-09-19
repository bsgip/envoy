from datetime import datetime, timezone
from typing import Optional

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import clone_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier
from sqlalchemy import func, select

from envoy.server.crud.subscription import (
    count_subscriptions_for_aggregator,
    count_subscriptions_for_site,
    delete_subscription_for_site,
    insert_subscription,
    select_subscription_by_id,
    select_subscriptions_for_aggregator,
    select_subscriptions_for_site,
)
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource


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
        assert sub_5.resource_id == 1
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
        assert sub_5.resource_id == 1
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
        # Test the aggregator end device query
        (1, None, 0, None, datetime.min, [1, 2, 4, 5]),
        (2, None, 0, None, datetime.min, [3]),
        (3, None, 0, None, datetime.min, []),
        # Test basic pagination
        (1, 4, 0, 1, datetime.min, [4]),
        (1, 4, 1, 1, datetime.min, [5]),
        (1, 4, 1, None, datetime.min, [5]),
        (1, None, 1, 2, datetime.min, [2, 4]),
        # Test datetime filter
        (1, 4, 0, None, datetime(2024, 1, 2, 12, 20, 0, tzinfo=timezone.utc), [4, 5]),
        (1, None, 0, None, datetime(2024, 1, 2, 12, 20, 0, tzinfo=timezone.utc), [2, 4, 5]),
        (1, 4, 0, None, datetime(2024, 1, 2, 15, 22, 33, tzinfo=timezone.utc), [5]),
        (1, None, 0, None, datetime(2024, 1, 2, 15, 22, 33, tzinfo=timezone.utc), [5]),
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
    site_id: Optional[int],
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
        assert sub_5.resource_id == 1
        assert sub_5.entity_limit == 55
        assert sub_5.notification_uri == "https://example.com:55/path/"
        assert len(sub_5.conditions) == 2
        assert sub_5.conditions[0].lower_threshold == 1
        assert sub_5.conditions[0].upper_threshold == 11
        assert sub_5.conditions[1].lower_threshold == 2
        assert sub_5.conditions[1].upper_threshold == 12


@pytest.mark.anyio
async def test_insert_subscription(pg_base_config):
    """Checks that sub inserting works as expected"""
    sub = Subscription(
        aggregator_id=1,
        changed_time=datetime.now(tz=timezone.utc),
        resource_type=SubscriptionResource.SITE,
        scoped_site_id=1,
        resource_id=None,
        notification_uri="http://test.insert/",
        entity_limit=555,
    )
    async with generate_async_session(pg_base_config) as session:
        # Clone so we dont end up with something tied to session
        sub_id = await insert_subscription(
            session, clone_class_instance(sub, ignored_properties=set(["aggregator", "conditions", "scoped_site"]))
        )
        assert sub_id > 0
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        new_sub = await select_subscription_by_id(session, 1, sub_id)
        assert_class_instance_equality(Subscription, sub, new_sub, ignored_properties=set(["subscription_id"]))


@pytest.mark.anyio
async def test_insert_subscription_with_condition(pg_base_config):
    """Checks that sub inserting works as expected"""
    condition = SubscriptionCondition(
        attribute=ConditionAttributeIdentifier.READING_VALUE, lower_threshold=22, upper_threshold=33
    )
    sub = Subscription(
        aggregator_id=1,
        changed_time=datetime.now(tz=timezone.utc),
        resource_type=SubscriptionResource.SITE,
        scoped_site_id=1,
        resource_id=None,
        notification_uri="http://test.insert/",
        entity_limit=555,
        conditions=[condition],
    )

    async with generate_async_session(pg_base_config) as session:
        # Clone so we dont end up with something tied to session
        cloned_sub: Subscription = clone_class_instance(
            sub, ignored_properties=set(["aggregator", "conditions", "scoped_site"])
        )
        cloned_sub.conditions = [clone_class_instance(condition, ignored_properties=set(["subscription"]))]
        sub_id = await insert_subscription(session, cloned_sub)
        assert sub_id > 0
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        new_sub = await select_subscription_by_id(session, 1, sub_id)
        assert_class_instance_equality(Subscription, sub, new_sub, ignored_properties=set(["subscription_id"]))
        assert_class_instance_equality(
            SubscriptionCondition,
            condition,
            new_sub.conditions[0],
            ignored_properties=set(["subscription_condition_id", "subscription_id"]),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "agg_id, site_id, sub_id, expected_deletion",
    [
        (1, None, 1, True),
        (1, 2, 2, True),
        (2, 3, 3, True),
        (2, None, 1, False),  # Bad Aggregator ID
        (99, None, 1, False),  # Bad Aggregator ID
        (2, 2, 2, False),  # Bad Aggregator ID
        (99, 2, 2, False),  # Bad Aggregator ID
        (1, 1, 1, False),  # Site ID is wrong
        (1, None, 2, False),  # Site ID missing
        (1, None, 99, False),  # Sub ID is wrong
    ],
)
async def test_delete_subscription_for_site_filter_values(
    pg_base_config, agg_id: int, site_id: Optional[int], sub_id: int, expected_deletion: bool
):
    """Tests the various ways we can filter down the deletion of a subscription"""
    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(Subscription)
        count_before = (await session.execute(stmt)).scalar_one()
        result = await delete_subscription_for_site(session, agg_id, site_id, sub_id)
        assert result == expected_deletion
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(Subscription)
        count_after = (await session.execute(stmt)).scalar_one()

        if expected_deletion:
            assert count_before == count_after + 1
        else:
            assert count_before == count_after


@pytest.mark.anyio
async def test_delete_subscription_for_site(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        assert await delete_subscription_for_site(session, 1, 4, 4)
        assert not await delete_subscription_for_site(session, 1, 4, 5)  # not scoped to site_id 4
        assert not await delete_subscription_for_site(session, 2, 2, 2)  # not scoped to agg 2
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        assert (
            await select_subscription_by_id(
                session,
                1,
                4,
            )
            is None
        ), "Was deleted"
        assert (
            await select_subscription_by_id(
                session,
                1,
                5,
            )
            is not None
        )
        assert (
            await select_subscription_by_id(
                session,
                1,
                2,
            )
            is not None
        )


@pytest.mark.anyio
async def test_delete_subscription_for_site_with_conditions(pg_base_config):
    # Start by updating our subscription 5 to appear under site 4 so we can delete it
    async with generate_async_session(pg_base_config) as session:
        sub_5 = await select_subscription_by_id(session, 1, 5)
        sub_5.scoped_site_id = 4

        resp = await session.execute(select(SubscriptionCondition))
        assert len(resp.scalars().all()) == 2
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        assert await delete_subscription_for_site(session, 1, 4, 5)  # not scoped to site_id 4
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        assert (
            await select_subscription_by_id(
                session,
                1,
                5,
            )
            is None
        ), "Was deleted"

    # Validate conditions got cascade deleted
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(SubscriptionCondition))
        assert len(resp.scalars().all()) == 0
