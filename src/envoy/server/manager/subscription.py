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
from envoy.server.request_state import RequestStateParameters

logger = logging.getLogger(__name__)


class SubscriptionManager:
    @staticmethod
    async def fetch_subscription_by_id(
        session: AsyncSession, request_params: RequestStateParameters, subscription_id: int, site_id: int
    ) -> Optional[Subscription]:
        """Fetches a subscription for a particular request (optionally scoped to a single site_id)

        site_id: If specified the returned sub must also have scoped_site set to this value
        """
        sub = await select_subscription_by_id(
            session, aggregator_id=request_params.aggregator_id, subscription_id=subscription_id
        )
        if sub is None:
            return None

        # non virtual site ids must align with the requested site id
        # or more simply - the virtual site can request any site subscription (within its aggregator)
        if site_id != VIRTUAL_END_DEVICE_SITE_ID and site_id != sub.scoped_site_id:
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
        site_id_filter: Optional[int] = site_id if site_id != VIRTUAL_END_DEVICE_SITE_ID else None

        sub_list = await select_subscriptions_for_site(
            session,
            aggregator_id=request_params.aggregator_id,
            site_id=site_id_filter,
            start=start,
            changed_after=after,
            limit=limit,
        )
        sub_count = await count_subscriptions_for_site(
            session,
            aggregator_id=request_params.aggregator_id,
            site_id=site_id_filter,
            changed_after=after,
        )

        return SubscriptionListMapper.map_to_site_response(
            rs_params=request_params, site_id=site_id, sub_list=sub_list, sub_count=sub_count
        )

    @staticmethod
    async def delete_subscription_for_site(
        session: AsyncSession, request_params: RequestStateParameters, site_id: int, subscription_id: int
    ) -> bool:
        """This will delete the specified subscription with id (underneath site_id) and return True if successful and
        False otherwise"""
        removed = await delete_subscription_for_site(
            session, aggregator_id=request_params.aggregator_id, site_id=site_id, subscription_id=subscription_id
        )
        await session.commit()

        logger.info(f"delete_subscription_for_site: site {site_id} subscription_id {subscription_id}")
        return removed

    @staticmethod
    async def add_subscription_for_site(
        session: AsyncSession, request_params: RequestStateParameters, subscription: Subscription, site_id: int
    ) -> int:
        """This will add the specified subscription to the database underneath site_id. Returns the inserted
        subscription id"""

        changed_time = utc_now()

        # We need the valid domains for the aggregator to validate our subscription
        aggregator = await select_aggregator(session, request_params.aggregator_id)
        if aggregator is None:
            raise NotFoundError(f"No aggregator with ID {request_params.aggregator_id} to receive subscription")
        valid_domains = set((d.domain for d in aggregator.domains))

        # We map - but we still need to validate the mapped subscription to ensure it's valid
        sub = SubscriptionMapper.map_from_request(
            subscription=subscription,
            rs_params=request_params,
            aggregator_domains=valid_domains,
            changed_time=changed_time,
        )

        # Validate site_id came through OK
        mapped_site_id_scope = sub.scoped_site_id if sub.scoped_site_id is not None else VIRTUAL_END_DEVICE_SITE_ID
        if mapped_site_id_scope != site_id:
            raise BadRequestError(
                f"Mismatch on subscribedResource EndDevice id {sub.scoped_site_id} expected {site_id}"
            )

        # If the subscription is for the virtual end device - we interpret that as not having a site id scope
        if sub.scoped_site_id == VIRTUAL_END_DEVICE_SITE_ID:
            sub.scoped_site_id = None

        # Lookup the linked entity (if any) to ensure it's accessible to this site
        if sub.resource_id is not None:
            if sub.resource_type == SubscriptionResource.READING:
                srt = await fetch_site_reading_type_for_aggregator(
                    session, request_params.aggregator_id, sub.resource_id, include_site_relation=False
                )
                if srt is None or (site_id != VIRTUAL_END_DEVICE_SITE_ID and srt.site_id != site_id):
                    raise BadRequestError(f"Invalid site_reading_type_id {sub.resource_id} for site {site_id}")
            elif sub.resource_type == SubscriptionResource.TARIFF_GENERATED_RATE:
                tp = await select_single_tariff(session, sub.resource_id)
                if tp is None:
                    raise BadRequestError(f"Invalid tariff_id {sub.resource_id} for site {site_id}")
            elif (
                sub.resource_type == SubscriptionResource.SITE_DER_AVAILABILITY
                or sub.resource_type == SubscriptionResource.SITE_DER_RATING
                or sub.resource_type == SubscriptionResource.SITE_DER_SETTING
                or sub.resource_type == SubscriptionResource.SITE_DER_STATUS
            ):
                if sub.resource_id != PUBLIC_SITE_DER_ID:
                    raise BadRequestError(f"Invalid der_id {sub.resource_id} for site {site_id}")
            else:
                raise BadRequestError("sub.resource_id is improperly set. Check subscribedResource is valid.")

        # Insert the subscription
        new_sub_id = await insert_subscription(session, sub)
        await session.commit()

        logger.info(f"add_subscription_for_site: site {site_id} new_sub_id {new_sub_id} type {sub.resource_type}")

        return new_sub_id
