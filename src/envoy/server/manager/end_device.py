import logging
from datetime import datetime
from secrets import token_bytes
from typing import Optional

from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.end_device import (
    get_virtual_site_for_aggregator,
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_single_site_with_sfdi,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.exception import ForbiddenError, UnableToGenerateIdError
from envoy.server.manager.time import utc_now
from envoy.server.mapper.csip_aus.connection_point import ConnectionPointMapper
from envoy.server.mapper.sep2.end_device import EndDeviceListMapper, EndDeviceMapper, VirtualEndDeviceMapper
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID
from envoy.server.model.site import Site
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import AggregatorRequestScope, RawRequestScope, SiteRequestScope

logger = logging.getLogger(__name__)


class EndDeviceManager:
    @staticmethod
    async def fetch_enddevice_for_scope(
        session: AsyncSession, scope: AggregatorRequestScope
    ) -> Optional[EndDeviceResponse]:
        # site_id of 0 refers to a virtual end-device (associated with the aggregator)
        if scope.site_id is None:
            site = await get_virtual_site_for_aggregator(
                session=session,
                aggregator_id=scope.aggregator_id,
                aggregator_lfdi=scope.lfdi,
            )
            if site is None:
                return None
            return VirtualEndDeviceMapper.map_to_response(scope, site)
        else:
            site = await select_single_site_with_site_id(
                session=session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
            )
            if site is None:
                return None
            return EndDeviceMapper.map_to_response(scope, site)

    @staticmethod
    async def generate_unique_device_id(session: AsyncSession, aggregator_id: int) -> tuple[int, str]:
        """Generates a unique sfdi/lfdi combination for the particular aggregator.

        Raises UnableToGenerateIdError if a sufficiently unique sfdi cannot be generated"""

        # ideally this would hook some form of TLS certificate generation process but given that we don't have a usecase
        # for envoy signing certificates (yet) we'll instead just rely on a good source of entropy and double check
        # the db (the double check on the DB might become relevant due to birthday paradox but I suspect this might
        # be a little overkill)

        # something has gone seriously wrong if we cant generate a new random value after this many attempts
        MAX_ATTEMPTS = 20
        for _ in range(MAX_ATTEMPTS):
            # We want 63 bits of randomness to avoid overflows when writing to db BIGINTEGER
            random_bytes = token_bytes(nbytes=8)
            random_bytes = bytes([random_bytes[0] & 0x7F]) + random_bytes[1:]
            candidate_sfdi = int.from_bytes(random_bytes, byteorder="big")
            existing_site = await select_single_site_with_sfdi(
                session, sfdi=candidate_sfdi, aggregator_id=aggregator_id
            )
            if existing_site is None:
                return (candidate_sfdi, f"{candidate_sfdi:x}")

        raise UnableToGenerateIdError(f"Unable to generate a unique sfdi within {MAX_ATTEMPTS} attempts. Failing.")

    @staticmethod
    async def add_or_update_enddevice_for_scope(
        session: AsyncSession, scope: RawRequestScope, end_device: EndDeviceRequest
    ) -> int:
        """This will add/update the specified end_device in the database.

        If the sfdi is unspecified they will be populated using generate_unique_device_id.

        This request uses the raw request scope but will ensure that the scope has permission to access the supplied
        site, raising ForbiddenError otherwise"""

        aggregator_id: Optional[int] = scope.aggregator_id
        if aggregator_id is None:
            # This will happen for a site registration from a device cert
            # In this case - the client is restricted to ONLY interact with the site with the same sfdi/lfdi
            if end_device.sFDI != scope.sfdi:
                raise ForbiddenError(f"sfdi mismatch. POST body: {end_device.sFDI} cert: {scope.sfdi}")
            if end_device.lFDI != scope.lfdi:
                raise ForbiddenError(f"lfdi mismatch. POST body: '{end_device.lFDI}' cert: '{scope.lfdi}'")
            aggregator_id = NULL_AGGREGATOR_ID  # Device certs go to null aggregator

        # Generate the sfdi if required (never do this for device certs)
        if end_device.sFDI is None or end_device.sFDI == 0 and scope.aggregator_id is not None:
            (sfdi, lfdi) = await EndDeviceManager.generate_unique_device_id(session, scope.aggregator_id)
            end_device.sFDI = sfdi
            if not end_device.lFDI:
                end_device.lFDI = lfdi  # Only update LFDI if not specified (i.e preserve what they send)
            logger.info(f"add_or_update_enddevice_for_aggregator: generated sfdi {sfdi} and lfdi {lfdi}")

        logger.info(
            f"add_or_update_enddevice_for_aggregator: upserting sfdi {end_device.sFDI} and lfdi {end_device.lFDI} for aggregator {aggregator_id}"  # noqa e501
        )
        changed_time = utc_now()
        site = EndDeviceMapper.map_from_request(end_device, aggregator_id, changed_time)
        result = await upsert_site_for_aggregator(session, aggregator_id, site)
        await session.commit()

        await NotificationManager.notify_upserted_entities(SubscriptionResource.SITE, changed_time)

        return result

    @staticmethod
    async def fetch_connection_point_for_site(
        session: AsyncSession, scope: SiteRequestScope
    ) -> Optional[ConnectionPointResponse]:
        """Given a site scoped request. Fetch the connection point associated with a particular site"""
        site = await select_single_site_with_site_id(
            session=session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
        )
        if site is None:
            return None
        return ConnectionPointMapper.map_to_response(site)

    @staticmethod
    async def update_nmi_for_site(session: AsyncSession, scope: SiteRequestScope, nmi: Optional[str]) -> bool:
        """Attempts to update the NMI for a designated site. Returns True if the update proceeded successfully,
        False if the Site doesn't exist / belongs to another aggregator_id"""

        changed_time = utc_now()
        site = await select_single_site_with_site_id(
            session=session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
        )
        if site is None:
            return False

        site.nmi = nmi
        site.changed_time = changed_time
        await session.commit()

        await NotificationManager.notify_upserted_entities(SubscriptionResource.SITE, changed_time)

        return True


class EndDeviceListManager:
    @staticmethod
    async def fetch_enddevicelist_for_scope(
        session: AsyncSession,
        scope: RawRequestScope,
        start: int,
        after: datetime,
        limit: int,
    ) -> EndDeviceListResponse:
        """
        This uses the raw request scope, a device cert will ONLY see their device (if registered)

        start = 0 return [virtual_site, site_1, site_2, site_3, ...]
        start = 1 return [site_1, site_2, site_3, ...]
        start = 2 return [site_2, site_3, ...]
        """
        agg_id: Optional[int] = scope.aggregator_id
        supports_virtual_site: bool = True
        virtual_site: Optional[Site] = None
        if agg_id is None:
            # Device certs can ONLY see their own device
            agg_id = NULL_AGGREGATOR_ID
            supports_virtual_site = False

        # Include the aggregator virtual site?
        if supports_virtual_site:
            if start == 0:
                # Get the virtual site associated with the aggregator
                virtual_site = await get_virtual_site_for_aggregator(
                    session=session,
                    aggregator_id=agg_id,
                    aggregator_lfdi=scope.lfdi,
                )

                # Adjust limit to account for the virtual site
                limit -= 1

            # Ensure a start value of either 0 or 1 will return the first site for the aggregator
            start = max(0, start - 1)

        # Are we selecting
        if scope.site_id is None:
            site_list = await select_all_sites_with_aggregator_id(session, agg_id, start, after, limit)
            site_count = await select_aggregator_site_count(session, agg_id, after)
        else:
            site = await select_single_site_with_site_id(session, scope.site_id, agg_id)
            if site:
                site_list = [site]
                site_count = 0
            else:
                site_list = []
                site_count = 0

        # site_count should include the virtual site
        if supports_virtual_site:
            site_count += 1

        return EndDeviceListMapper.map_to_response(
            scope=scope, site_list=site_list, site_count=site_count, virtual_site=virtual_site
        )
