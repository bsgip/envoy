from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
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


async def upsert_subscription(session: AsyncSession, subscription: Subscription) -> int:
    """Inserts (or updates) the specified subscription (and any linked conditions) into the database.

    Renewals will guarantee that the existing subscription ID will remain the same (with updated changed_time)

    Inserts will generate a new subscription ID

    Returns the new (or existing) subscription_id"""

    resource_id_clause = (
        Subscription.resource_id.is_(None)
        if subscription.resource_id is None
        else (Subscription.resource_id == subscription.resource_id)
    )

    scoped_site_id_clause = (
        Subscription.scoped_site_id.is_(None)
        if subscription.scoped_site_id is None
        else (Subscription.scoped_site_id == subscription.scoped_site_id)
    )

    # Step 1 - Identify if we have a "clash". If we do, then this is a "renewal" rather than a whole new subscription
    # Getting this into a unique constraint in the DB is tricky due to the nullability of the resource_id
    # So we just manage this directly - it should be efficient "enough" with existing indexes
    existing_sub = (
        await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.aggregator_id == subscription.aggregator_id,
                    Subscription.resource_type == subscription.resource_type,
                    scoped_site_id_clause,
                    resource_id_clause,
                )
            )
            .order_by(Subscription.subscription_id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Step 2 [Optional] - If we have an existing subscription ID, we'll need to archive it in its current state and
    # also delete any conditions (they'll be replaced)
    if existing_sub is not None:
        await copy_rows_into_archive(
            session,
            Subscription,
            ArchiveSubscription,
            lambda q: q.where(Subscription.subscription_id == existing_sub.subscription_id),
        )
        await copy_rows_into_archive(
            session,
            SubscriptionCondition,
            ArchiveSubscriptionCondition,
            lambda q: q.where(SubscriptionCondition.subscription_id == existing_sub.subscription_id),
        )
        # Clear out any existing conditions (we're about to reinsert them as if they were updated)
        await session.execute(
            delete(SubscriptionCondition).where(SubscriptionCondition.subscription_id == existing_sub.subscription_id)
        )

    # Step 3 - massage our entity to be a "new" insert or an update to an existing record
    if existing_sub is None:
        # This is a brand new subscription - clear out the created_time so the DB can generate it
        if subscription.created_time:
            del subscription.created_time
        if subscription.subscription_id:
            del subscription.subscription_id

        # Insert Subscription (and any child conditions)
        session.add(subscription)

        await session.flush()
        return subscription.subscription_id
    else:
        # Update subscription (and insert new child conditions)
        existing_sub.changed_time = subscription.changed_time
        existing_sub.entity_limit = subscription.entity_limit
        existing_sub.notification_uri = subscription.notification_uri

        if subscription.conditions is not None:
            for c in subscription.conditions:
                c.subscription = existing_sub
                session.add(c)

        await session.flush()
        return existing_sub.subscription_id
