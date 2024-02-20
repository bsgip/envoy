from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.pub_sub import Subscription, SubscriptionListResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.subscription import select_subscription_by_id
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

        if site_id is not None and sub.scoped_site != site_id:
            return None

        # site = await select_single_site_with_site_id(
        #     session=session, site_id=site_id, aggregator_id=request_params.aggregator_id
        # )
        # if site is None:
        #     return None
        # return EndDeviceMapper.map_to_response(request_params, site)
        raise NotImplementedError()

    @staticmethod
    async def fetch_subscriptions_for_site(
        session: AsyncSession,
        request_params: RequestStateParameters,
        start: int,
        after: datetime,
        limit: int,
    ) -> SubscriptionListResponse:
        # site_list = await select_all_sites_with_aggregator_id(
        #     session, request_params.aggregator_id, start, after, limit
        # )
        # site_count = await select_aggregator_site_count(session, request_params.aggregator_id, after)
        # return EndDeviceListMapper.map_to_response(request_params, site_list, site_count)
        raise NotImplementedError()
