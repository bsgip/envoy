from datetime import datetime
from secrets import token_bytes
from typing import Optional

from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse
from envoy_schema.server.schema.sep2.der import (
    DER,
    AlarmStatusType,
    ConnectStatusType,
    DERAvailability,
    DERCapability,
    DERControlType,
    DERListResponse,
    DERSettings,
    DERStatus,
)
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.der import generate_default_site_der, select_site_der_for_site
from envoy.server.crud.end_device import (
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_single_site_with_sfdi,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.exception import NotFoundError, UnableToGenerateIdError
from envoy.server.manager.time import utc_now
from envoy.server.mapper.csip_aus.connection_point import ConnectionPointMapper
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID
from envoy.server.mapper.sep2.der import DERCapabilityMapper, DERMapper
from envoy.server.mapper.sep2.end_device import EndDeviceListMapper, EndDeviceMapper
from envoy.server.model.site import SiteDER
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_state import RequestStateParameters

PUBLIC_SITE_DER_ID = 1  # We won't be exposing the DER id (csip aus implies only having a single DER per site)

STATIC_POLL_RATE_SECONDS = 300  # This should eventually migrate to a config option / dynamic value


async def site_der_for_site(session: AsyncSession, aggregator_id: int, site_id: int) -> SiteDER:
    """Utility for fetching the SiteDER for the specified site. If nothing is in the database, returns the
    default site der.

    Raises NotFoundError if site_id is missing / not accessible"""
    site_der = await select_site_der_for_site(session=session, site_id=site_id, aggregator_id=aggregator_id)
    if site_der is None:
        # Validate the site exists / is accessible first
        site = await select_single_site_with_site_id(session, site_id, aggregator_id)
        if site is None:
            raise NotFoundError(f"site with id {site_id} not found")
        site_der = generate_default_site_der(site_id, site.changed_time)

    return site_der


class DERManager:
    @staticmethod
    async def fetch_der_list_for_site(
        session: AsyncSession,
        site_id: int,
        request_params: RequestStateParameters,
        start: int,
        limit: int,
        after: datetime,
    ) -> DERListResponse:
        """Provides a list view of DER for a specific site. Raises NotFoundError if DER/Site couldn't be accessed"""

        # If there isn't custom DER info already in place - return a default
        site_der = await site_der_for_site(session, request_params.aggregator_id, site_id)
        site_der.site_der_id = PUBLIC_SITE_DER_ID

        # Manually filter - we are forcing our single DER into a simple list
        ders: list[tuple[SiteDER, Optional[str]]]
        total: int
        if after > site_der.changed_time:
            ders = []
            total = 0
        elif start > 0 or limit < 1:
            ders = []
            total = 1
        else:
            ders = [(site_der, DOE_PROGRAM_ID)]
            total = 1

        return DERMapper.map_to_list_response(request_params, site_id, STATIC_POLL_RATE_SECONDS, ders, total)

    @staticmethod
    async def fetch_der_for_site(
        session: AsyncSession,
        site_id: int,
        site_der_id: int,
        request_params: RequestStateParameters,
    ) -> DER:
        """Fetches a single DER for a specific site. Raises NotFoundError if DER/Site couldn't be accessed"""

        site_der = await site_der_for_site(session, request_params.aggregator_id, site_id)
        site_der.site_der_id = PUBLIC_SITE_DER_ID

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {site_id}")

        return DERMapper.map_to_response(request_params, site_der, DOE_PROGRAM_ID)


class DERCapabilityManager:

    @staticmethod
    async def fetch_der_capability_for_site(
        session: AsyncSession,
        site_id: int,
        site_der_id: int,
        request_params: RequestStateParameters,
    ) -> DERCapability:
        """Fetches a single DER Capability for a specific DER. Raises NotFoundError if DER/Site couldn't be accessed
        or if no DERCapability has been stored."""

        site_der = await site_der_for_site(session, request_params.aggregator_id, site_id)
        site_der.site_der_id = PUBLIC_SITE_DER_ID

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {site_id}")

        if site_der.site_der_rating is None:
            raise NotFoundError(f"no DERCapability on record for DER {site_der_id} in site {site_id}")

        return DERCapabilityMapper.map_to_response(request_params, site_id, site_der.site_der_rating)

    @staticmethod
    async def upsert_der_capability_for_site(
        session: AsyncSession,
        site_id: int,
        site_der_id: int,
        request_params: RequestStateParameters,
        der_capability: DERCapability,
    ) -> None:
        """Handles creating/updating the DERCapability for the specified site der. Raises NotFoundError
        if the site/der can't be found"""

        if site_der_id != PUBLIC_SITE_DER_ID:
            raise NotFoundError(f"no DER with id {site_der_id} in site {site_id}")

        now = utc_now()
        new_der_rating = DERCapabilityMapper.map_from_request(now, der_capability)

        site_der = await site_der_for_site(session, request_params.aggregator_id, site_id)
        if site_der.site_der_id is None:
            # we are inserting a whole new DER and rating
            site_der.site_der_rating = new_der_rating
            session.add(site_der)
            await session.commit()
        elif site_der.site_der_rating is None:
            # we are inserting a new rating
            new_der_rating.site_der_id = site_der.site_der_id
            site_der.site_der_rating = new_der_rating
            await session.commit()
        else:
            # we are updating an existing rating
            new_der_rating.site_der_id = site_der.site_der_id
            new_der_rating.site_der_rating_id = site_der.site_der_rating.site_der_rating_id
            await session.merge(new_der_rating)
            await session.commit()
