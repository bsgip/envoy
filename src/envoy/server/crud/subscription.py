from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.crud.archive import delete_rows_into_archive
from envoy.server.model.archive.subscription import ArchiveSubscription, ArchiveSubscriptionCondition
from envoy.server.model.subscription import Subscription, SubscriptionCondition


async def select_subscription_by_id(
    session: AsyncSession, aggregator_id: int, subscription_id: int
) -> Optional[Subscription]:
    """Selects the subscription with the specified subscription_id. Returns None if the entity doesn't exist for the
    specified aggregator. Will include Conditions"""

    stmt = (
        select(Subscription)
        .where((Subscription.subscription_id == subscription_id) & (Subscription.aggregator_id == aggregator_id))
        .options(selectinload(Subscription.conditions))
    )

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_subscriptions_for_aggregator(
    session: AsyncSession,
    aggregator_id: int,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Sequence[Subscription]:
    """Selects subscriptions for an aggregator. Will include Conditions

    Orders by sep2 requirements on Subscription which is id ASC"""

    stmt = (
        select(Subscription)
        .where((Subscription.aggregator_id == aggregator_id) & (Subscription.changed_time >= changed_after))
        .options(selectinload(Subscription.conditions))
        .order_by(Subscription.subscription_id)
        .offset(start)
        .limit(limit)
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_subscriptions_for_aggregator(
    session: AsyncSession,
    aggregator_id: int,
    changed_after: datetime,
) -> int:
    """Similar to select_subscriptions_for_aggregator but instead returns a count"""

    stmt = (
        select(func.count())
        .select_from(Subscription)
        .where((Subscription.aggregator_id == aggregator_id) & (Subscription.changed_time >= changed_after))
    )

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_subscriptions_for_site(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Sequence[Subscription]:
    """Selects subscriptions that are scoped to a single site within an aggregator. Will include Conditions

    Orders by sep2 requirements on Subscription which is id ASC"""

    stmt = (
        select(Subscription)
        .where((Subscription.aggregator_id == aggregator_id) & (Subscription.changed_time >= changed_after))
        .options(selectinload(Subscription.conditions))
        .order_by(Subscription.subscription_id)
        .offset(start)
        .limit(limit)
    )

    if site_id is not None:
        stmt = stmt.where(Subscription.scoped_site_id == site_id)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_subscriptions_for_site(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    changed_after: datetime,
) -> int:
    """Similar to select_subscriptions_for_site but instead returns a count"""

    stmt = (
        select(func.count())
        .select_from(Subscription)
        .where((Subscription.aggregator_id == aggregator_id) & (Subscription.changed_time >= changed_after))
    )

    if site_id is not None:
        stmt = stmt.where(Subscription.scoped_site_id == site_id)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def delete_subscription_for_site(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], subscription_id: int, deleted_time: datetime
) -> bool:
    """Deletes the specified subscription (and any linked conditions) from the database. Returns true on successful
    delete

    site_id: If None - will match Subscription.scoped_site_id = None otherwise will match value for value

    Existing subscriptions details will be archived"""

    # We can't just roll in and delete the SubscriptionConditions without validating that the parent subscription
    # belongs to aggregator/site_id (otherwise we could allow indiscriminate deletions of SubscriptionConditions)
    fetch_count_stmt = (
        select(func.count())
        .select_from(Subscription)
        .where((Subscription.subscription_id == subscription_id) & (Subscription.aggregator_id == aggregator_id))
    )
    if site_id is None:
        fetch_count_stmt = fetch_count_stmt.where(Subscription.scoped_site_id.is_(None))
    else:
        fetch_count_stmt = fetch_count_stmt.where(Subscription.scoped_site_id == site_id)
    if (await session.execute(fetch_count_stmt)).scalar_one() != 1:
        return False

    # At this point we're certain that the subscription exists AND belongs to the aggregator/site
    # We're free to start deleting/archiving the parts

    await delete_rows_into_archive(
        session,
        SubscriptionCondition,
        ArchiveSubscriptionCondition,
        deleted_time,
        lambda q: q.where(SubscriptionCondition.subscription_id == subscription_id),
    )
    await delete_rows_into_archive(
        session,
        Subscription,
        ArchiveSubscription,
        deleted_time,
        lambda q: q.where(Subscription.subscription_id == subscription_id),
    )

    return True


async def insert_subscription(session: AsyncSession, subscription: Subscription) -> int:
    """Inserts the specified subscription (and any linked conditions) into the database - wont persist until
    session is committed. Returns the new subscription_id"""

    if subscription.created_time:
        del subscription.created_time  # let the DB generate this
    session.add(subscription)
    await session.flush()
    return subscription.subscription_id
