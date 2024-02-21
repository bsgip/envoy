from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.subscription import Subscription


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
    site_id: int,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Sequence[Subscription]:
    """Selects subscriptions that are scoped to a single site within an aggregator. Will include Conditions

    Orders by sep2 requirements on Subscription which is id ASC"""

    stmt = (
        select(Subscription)
        .where(
            (Subscription.aggregator_id == aggregator_id)
            & (Subscription.changed_time >= changed_after)
            & (Subscription.scoped_site_id == site_id)
        )
        .options(selectinload(Subscription.conditions))
        .order_by(Subscription.subscription_id)
        .offset(start)
        .limit(limit)
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_subscriptions_for_site(
    session: AsyncSession,
    aggregator_id: int,
    site_id: int,
    changed_after: datetime,
) -> int:
    """Similar to select_subscriptions_for_site but instead returns a count"""

    stmt = (
        select(func.count())
        .select_from(Subscription)
        .where(
            (Subscription.aggregator_id == aggregator_id)
            & (Subscription.changed_time >= changed_after)
            & (Subscription.scoped_site_id == site_id)
        )
    )

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def insert_subscription(session: AsyncSession, subscription: Subscription) -> None:
    """Inserts the specified subscription (and any linked conditions) into the database - wont persist until
    session is committed"""
    session.add(subscription)