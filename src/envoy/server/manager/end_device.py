import logging
import os
from datetime import datetime
from secrets import randbelow, token_bytes
from typing import Optional, Sequence

from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse
from envoy_schema.server.schema.sep2.end_device import (
    EndDeviceListResponse,
    EndDeviceRequest,
    EndDeviceResponse,
    RegistrationResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.archive import copy_rows_into_archive
from envoy.server.crud.end_device import (
    delete_site_for_aggregator,
    get_virtual_site_for_aggregator,
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_single_site_with_lfdi,
    select_single_site_with_sfdi,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.exception import ForbiddenError, NotFoundError, UnableToGenerateIdError
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.manager.time import utc_now
from envoy.server.mapper.csip_aus.connection_point import ConnectionPointMapper
from envoy.server.mapper.sep2.end_device import (
    EndDeviceListMapper,
    EndDeviceMapper,
    RegistrationMapper,
    VirtualEndDeviceMapper,
)
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.site import Site
from envoy.server.model.subscription import SubscriptionResource
from envoy.server.request_scope import (
    CertificateType,
    DeviceOrAggregatorRequestScope,
    SiteRequestScope,
    UnregisteredRequestScope,
)

MAX_REGISTRATION_PIN = 99999

logger = logging.getLogger(__name__)


async def fetch_sites_and_count_for_claims(
    session: AsyncSession,
    scope: UnregisteredRequestScope,
    start: int,
    after: datetime,
    limit: int,
) -> tuple[Sequence[Site], int]:

    # Are we selecting all sites for an aggregator or are we scoped to a particular site
    if scope.source == CertificateType.DEVICE_CERTIFICATE:
        site_list: Sequence[Site] = []
        site_count: int = 0
        site = await select_single_site_with_lfdi(
            session,
            scope.lfdi,
            scope.aggregator_id,
        )

        if site and site.changed_time > after:
            # We have a site (and it's not filtered out) - now apply our "virtual" pagination
            if start == 0 and limit > 0:
                return ([site], 1)  # If pagination allows the first record through - send it
            else:
                return (
                    [],
                    1,
                )  # pagination isn't fetching the first element in the list, return empty but list total
        else:
            # If we are here - there either isn't a registered site OR it's been filtered by the query. Return empty
            return ([], 0)
    elif scope.source == CertificateType.AGGREGATOR_CERTIFICATE:
        site_list = await select_all_sites_with_aggregator_id(session, scope.aggregator_id, start, after, limit)
        site_count = await select_aggregator_site_count(session, scope.aggregator_id, after)
        return (site_list, site_count)
    else:
        raise ValueError(f"Unsupported scope source: {scope.source}")


class EndDeviceManager:
    @staticmethod
    async def fetch_enddevice_for_scope(
        session: AsyncSession, scope: DeviceOrAggregatorRequestScope
    ) -> Optional[EndDeviceResponse]:

        # site_id of 0 refers to a virtual end-device (associated with the aggregator)
        if scope.site_id is None:
            site = await get_virtual_site_for_aggregator(
                session=session,
                aggregator_id=scope.aggregator_id,
                aggregator_lfdi=scope.lfdi,
                post_rate_seconds=None,
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

            config = await RuntimeServerConfigManager.fetch_current_config(session)
            return EndDeviceMapper.map_to_response(scope, site, config.disable_edev_registration)

    @staticmethod
    async def delete_enddevice_for_scope(session: AsyncSession, scope: SiteRequestScope) -> bool:
        """Deletes the specified site and all child dependencies of that site. Deleted records will be archived
        as necessary. Returns True if the delete removed something, False if the site DNE / is inaccessible.

        This will commit the transaction in session"""

        delete_time = utc_now()
        result = await delete_site_for_aggregator(
            session, aggregator_id=scope.aggregator_id, site_id=scope.site_id, deleted_time=delete_time
        )
        await session.commit()

        # We only notify the top level site deletion - all the child entities will be overwhelming
        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE, delete_time)

        return result

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
    def lfdi_matches(a: Optional[str], b: Optional[str]) -> bool:
        """Case insensitive matching of LFDIs"""
        return (None if a is None else a.lower()) == (None if b is None else b.lower())

    @staticmethod
    async def add_or_update_enddevice_for_scope(
        session: AsyncSession, scope: UnregisteredRequestScope, end_device: EndDeviceRequest
    ) -> int:
        """This will add/update the specified end_device in the database.

        If the sfdi is unspecified they will be populated using generate_unique_device_id.

        This request uses the raw request scope but will ensure that the scope has permission to access the supplied
        site, raising ForbiddenError otherwise"""
        is_device_cert = scope.source == CertificateType.DEVICE_CERTIFICATE
        if is_device_cert:
            # This will happen for a site registration from a device cert
            # In this case - the client is restricted to ONLY interact with the site with the same sfdi/lfdi
            if end_device.sFDI != scope.sfdi:
                raise ForbiddenError(f"sfdi mismatch. POST body: {end_device.sFDI} cert: {scope.sfdi}")
            if not EndDeviceManager.lfdi_matches(end_device.lFDI, scope.lfdi):
                raise ForbiddenError(f"lfdi mismatch. POST body: '{end_device.lFDI}' cert: '{scope.lfdi}'")

        # Generate the sfdi if required (never do this for device certs)
        if end_device.sFDI is None or end_device.sFDI == 0 and not is_device_cert:
            (sfdi, lfdi) = await EndDeviceManager.generate_unique_device_id(session, scope.aggregator_id)
            end_device.sFDI = sfdi
            if not end_device.lFDI:
                end_device.lFDI = lfdi  # Only update LFDI if not specified (i.e preserve what they send)
            logger.info(f"add_or_update_enddevice_for_aggregator: generated sfdi {sfdi} and lfdi {lfdi}")

        logger.info(
            f"add_or_update_enddevice_for_aggregator: upserting sfdi {end_device.sFDI} and lfdi {end_device.lFDI} for aggregator {scope.aggregator_id}"  # noqa e501
        )
        changed_time = utc_now()
        registration_pin = RegistrationManager.generate_registration_pin()  # This will only apply to INSERTED sites
        site = EndDeviceMapper.map_from_request(end_device, scope.aggregator_id, changed_time, registration_pin)
        result = await upsert_site_for_aggregator(session, scope.aggregator_id, site)
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE, changed_time)

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

        # Ensure we archive the existing data
        await copy_rows_into_archive(session, Site, ArchiveSite, lambda q: q.where(Site.site_id == site.site_id))

        site.nmi = nmi
        site.changed_time = changed_time
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE, changed_time)

        return True

    @staticmethod
    async def fetch_enddevicelist_for_scope(
        session: AsyncSession,
        scope: UnregisteredRequestScope,
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
        virtual_site: Optional[Site] = None
        includes_virtual_site = scope.source == CertificateType.AGGREGATOR_CERTIFICATE

        # Include the aggregator virtual site?
        if includes_virtual_site:
            if start == 0:
                if limit > 0:
                    # Get the virtual site associated with the aggregator
                    virtual_site = await get_virtual_site_for_aggregator(
                        session=session,
                        aggregator_id=scope.aggregator_id,
                        aggregator_lfdi=scope.lfdi,
                        post_rate_seconds=None,
                    )

                # Adjust limit to account for the virtual site
                limit = max(0, limit - 1)

            # Ensure a start value of either 0 or 1 will return the first site for the aggregator
            start = max(0, start - 1)

        # Are we selecting all sites for an aggregator or are we scoped to a particular site
        (site_list, site_count) = await fetch_sites_and_count_for_claims(session, scope, start, after, limit)

        # site_count should include the virtual site
        if includes_virtual_site:
            site_count += 1

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return EndDeviceListMapper.map_to_response(
            scope=scope,
            site_list=site_list,
            site_count=site_count,
            virtual_site=virtual_site,
            disable_registration=config.disable_edev_registration,
            pollrate_seconds=config.edevl_pollrate_seconds,
        )


class RegistrationManager:

    @staticmethod
    def generate_registration_pin() -> int:
        """Generates a random integer from 0 -> 99999 (5 digits) that can be used as a end device registration PIN.
        No guarantees about uniqueness are made"""
        raw_static_pin = os.environ.get("STATIC_REGISTRATION_PIN", "")
        if raw_static_pin:
            try:
                return int(raw_static_pin)
            except ValueError as exc:
                logger.error(
                    f"Failure reading STATIC_REGISTRATION_PIN env variable '{raw_static_pin}' as an in", exc_info=exc
                )
                return 0

        return randbelow(MAX_REGISTRATION_PIN + 1)  # The upper bound is exclusive so +1 allows us to generate 99999

    @staticmethod
    async def fetch_registration_for_scope(session: AsyncSession, scope: SiteRequestScope) -> RegistrationResponse:
        """Fetches the sep2 Registration associated with an existing site. If that site is NOT accessible, NotFound
        will be raised"""
        site = await select_single_site_with_site_id(
            session=session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
        )
        if site is None:
            raise NotFoundError(f"Site {scope.site_id} either doesn't exist or is inaccessible to this client.")

        return RegistrationMapper.map_to_response(scope, site)
