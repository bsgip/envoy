from datetime import datetime, timezone
from secrets import token_bytes
from typing import Optional

from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.api.request import RequestStateParameters
from envoy.server.crud.end_device import (
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_single_site_with_sfdi,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.exception import UnableToGenerateIdError
from envoy.server.mapper.csip_aus.connection_point import ConnectionPointMapper
from envoy.server.mapper.sep2.end_device import EndDeviceListMapper, EndDeviceMapper


class EndDeviceManager:
    @staticmethod
    async def fetch_enddevice_with_site_id(
        session: AsyncSession, site_id: int, request_params: RequestStateParameters
    ) -> Optional[EndDeviceResponse]:
        site = await select_single_site_with_site_id(
            session=session, site_id=site_id, aggregator_id=request_params.aggregator_id
        )
        if site is None:
            return None
        return EndDeviceMapper.map_to_response(request_params, site)

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
    async def add_or_update_enddevice_for_aggregator(
        session: AsyncSession, request_params: RequestStateParameters, end_device: EndDeviceRequest
    ) -> int:
        """This will add/update the specified end_device in the database. If the sfdi is unspecified
        they will be populated using generate_unique_device_id"""

        # Generate the sfdi if required
        if end_device.sFDI is None or end_device.sFDI == 0:
            (sfdi, lfdi) = await EndDeviceManager.generate_unique_device_id(session, request_params.aggregator_id)
            end_device.sFDI = sfdi
            end_device.lFDI = lfdi

        site = EndDeviceMapper.map_from_request(end_device, request_params.aggregator_id, datetime.now(tz=timezone.utc))
        result = await upsert_site_for_aggregator(session, request_params.aggregator_id, site)
        await session.commit()
        return result

    @staticmethod
    async def fetch_connection_point_for_site(
        session: AsyncSession, site_id: int, request_params: RequestStateParameters
    ) -> Optional[ConnectionPointResponse]:
        """Given a site ID and requesting aggregator. Fetch the connection point associated with a particular site"""
        site = await select_single_site_with_site_id(
            session=session, site_id=site_id, aggregator_id=request_params.aggregator_id
        )
        if site is None:
            return None
        return ConnectionPointMapper.map_to_response(site)

    @staticmethod
    async def update_nmi_for_site(
        session: AsyncSession, request_params: RequestStateParameters, site_id: int, nmi: Optional[str]
    ) -> bool:
        """Attempts to update the NMI for a designated site. Returns True if the update proceeded successfully,
        False if the Site doesn't exist / belongs to another aggregator_id"""

        site = await select_single_site_with_site_id(
            session=session, site_id=site_id, aggregator_id=request_params.aggregator_id
        )
        if site is None:
            return False

        site.nmi = nmi
        site.changed_time = datetime.now(tz=timezone.utc)
        await session.commit()
        return True


class EndDeviceListManager:
    @staticmethod
    async def fetch_enddevicelist_with_aggregator_id(
        session: AsyncSession,
        request_params: RequestStateParameters,
        start: int,
        after: datetime,
        limit: int,
    ) -> EndDeviceListResponse:
        site_list = await select_all_sites_with_aggregator_id(
            session, request_params.aggregator_id, start, after, limit
        )
        site_count = await select_aggregator_site_count(session, request_params.aggregator_id, after)
        return EndDeviceListMapper.map_to_response(request_params, site_list, site_count)
