import logging
from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.pub_sub import Subscription, SubscriptionListResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.aggregator import select_aggregator
from envoy.server.crud.end_device import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.crud.pricing import select_single_tariff
from envoy.server.crud.site_reading import fetch_site_reading_type_for_aggregator
from envoy.server.crud.subscription import (
    count_subscriptions_for_site,
    delete_subscription_for_site,
    insert_subscription,
    select_subscription_by_id,
    select_subscriptions_for_site,
)
from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.manager.time import utc_now
from envoy.server.mapper.sep2.pub_sub import SubscriptionListMapper, SubscriptionMapper
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import AggregatorRequestScope

logger = logging.getLogger(__name__)


class SubscriptionManager:
    @staticmethod
    async def fetch_subscription_by_id(
        session: AsyncSession, scope: AggregatorRequestScope, subscription_id: int
    ) -> Optional[Subscription]:
        """Fetches a subscription for a particular request (optionally scoped to a single site_id)

        site_id: If specified the returned sub must also have scoped_site set to this value
        """
        sub = await select_subscription_by_id(
            session, aggregator_id=scope.aggregator_id, subscription_id=subscription_id
        )
        if sub is None:
            return None

        # non virtual site ids must align with the requested site id
        # or more simply - the virtual site can request any site subscription (within its aggregator)
        if scope.site_id is not None and scope.site_id != sub.scoped_site_id:
            return None

        return SubscriptionMapper.map_to_response(sub, scope)

    @staticmethod
    async def fetch_subscriptions_for_site(
        session: AsyncSession,
        scope: AggregatorRequestScope,
        start: int,
        after: datetime,
        limit: int,
    ) -> SubscriptionListResponse:
        """Fetches all subscriptions underneath the specified site"""

        sub_list = await select_subscriptions_for_site(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            start=start,
            changed_after=after,
            limit=limit,
        )
        sub_count = await count_subscriptions_for_site(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            changed_after=after,
        )

        return SubscriptionListMapper.map_to_site_response(scope=scope, sub_list=sub_list, sub_count=sub_count)

    @staticmethod
    async def delete_subscription_for_site(
        session: AsyncSession, scope: AggregatorRequestScope, subscription_id: int
    ) -> bool:
        """This will delete the specified subscription with id (underneath site_id) and return True if successful and
        False otherwise"""
        now = utc_now()
        removed = await delete_subscription_for_site(
            session,
            aggregator_id=scope.aggregator_id,
            site_id=scope.site_id,
            subscription_id=subscription_id,
            deleted_time=now,
        )
        await session.commit()

        logger.info(f"delete_subscription_for_site: site {scope.site_id} subscription_id {subscription_id}")
        return removed

    @staticmethod
    async def add_subscription_for_site(
        session: AsyncSession, scope: AggregatorRequestScope, subscription: Subscription
    ) -> int:
        """This will add the specified subscription to the database underneath site_id. Returns the inserted
        subscription id"""

        changed_time = utc_now()

        # We need the valid domains for the aggregator to validate our subscription
        aggregator = await select_aggregator(session, scope.aggregator_id)
        if aggregator is None:
            raise NotFoundError(f"No aggregator with ID {scope.aggregator_id} to receive subscription")
        valid_domains = set((d.domain for d in aggregator.domains))

        # We map - but we still need to validate the mapped subscription to ensure it's valid
        sub = SubscriptionMapper.map_from_request(
            subscription=subscription,
            scope=scope,
            aggregator_domains=valid_domains,
            changed_time=changed_time,
        )

        # If the subscription is for the virtual end device - we interpret that as not having a site id scope
        if sub.scoped_site_id == VIRTUAL_END_DEVICE_SITE_ID:
            sub.scoped_site_id = None

        # Validate site_id came through OK
        if sub.scoped_site_id != scope.site_id:
            raise BadRequestError(
                f"Mismatch on subscribedResource EndDevice id {sub.scoped_site_id} expected {scope.site_id}"
            )

        # Lookup the linked entity (if any) to ensure it's accessible to this site
        if sub.resource_id is not None:
            if sub.resource_type == SubscriptionResource.READING:
                srt = await fetch_site_reading_type_for_aggregator(
                    session, scope.aggregator_id, sub.resource_id, scope.site_id, include_site_relation=False
                )
                if srt is None:
                    raise BadRequestError(f"Invalid site_reading_type_id {sub.resource_id} for site {scope.site_id}")
            elif sub.resource_type == SubscriptionResource.TARIFF_GENERATED_RATE:
                tp = await select_single_tariff(session, sub.resource_id)
                if tp is None:
                    raise BadRequestError(f"Invalid tariff_id {sub.resource_id} for site {scope.site_id}")
            elif (
                sub.resource_type == SubscriptionResource.SITE_DER_AVAILABILITY
                or sub.resource_type == SubscriptionResource.SITE_DER_RATING
                or sub.resource_type == SubscriptionResource.SITE_DER_SETTING
                or sub.resource_type == SubscriptionResource.SITE_DER_STATUS
            ):
                if sub.resource_id != PUBLIC_SITE_DER_ID:
                    raise BadRequestError(f"Invalid der_id {sub.resource_id} for site {scope.site_id}")
            else:
                raise BadRequestError("sub.resource_id is improperly set. Check subscribedResource is valid.")

        # Insert the subscription
        new_sub_id = await insert_subscription(session, sub)
        await session.commit()

        logger.info(f"add_subscription_for_site: site {scope.site_id} new_sub_id {new_sub_id} type {sub.resource_type}")

        return new_sub_id
