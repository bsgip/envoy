from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.pub_sub import Subscription, SubscriptionListResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.subscription import (
    count_subscriptions_for_site,
    select_subscription_by_id,
    select_subscriptions_for_site,
)
from envoy.server.mapper.sep2.pub_sub import SubscriptionListMapper, SubscriptionMapper
from envoy.server.request_state import RequestStateParameters


class SubscriptionManager:
    @staticmethod
    async def fetch_subscription_by_id(
        session: AsyncSession, request_params: RequestStateParameters, subscription_id: int, site_id: Optional[int]
    ) -> Optional[Subscription]:
        """Fetches a subscription for a particular request (optionally scoped to a single site_id)

        site_id: If specified the returned sub must also have scoped_site set to this value
        """
        sub = await select_subscription_by_id(
            session, aggregator_id=request_params.aggregator_id, subscription_id=subscription_id
        )
        if sub is None:
            return None

        if site_id is not None and sub.scoped_site_id != site_id:
            return None

        return SubscriptionMapper.map_to_response(sub, request_params)

    @staticmethod
    async def fetch_subscriptions_for_site(
        session: AsyncSession,
        request_params: RequestStateParameters,
        site_id: int,
        start: int,
        after: datetime,
        limit: int,
    ) -> SubscriptionListResponse:
        """Fetches all subscriptions underneath the specified site"""
        sub_list = await select_subscriptions_for_site(
            session,
            aggregator_id=request_params.aggregator_id,
            site_id=site_id,
            start=start,
            changed_after=after,
            limit=limit,
        )
        sub_count = await count_subscriptions_for_site(
            session,
            aggregator_id=request_params.aggregator_id,
            site_id=site_id,
            changed_after=after,
        )

        return SubscriptionListMapper.map_to_site_response(
            rs_params=request_params, site_id=site_id, sub_list=sub_list, sub_count=sub_count
        )
