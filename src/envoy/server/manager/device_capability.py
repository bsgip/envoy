from typing import Optional

from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud import link
from envoy.server.crud.end_device import select_single_site_with_lfdi
from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.request_scope import CertificateType, UnregisteredRequestScope


class DeviceCapabilityManager:
    @staticmethod
    async def fetch_device_capability(
        session: AsyncSession, scope: UnregisteredRequestScope
    ) -> DeviceCapabilityResponse:
        """Noting this operates on a RawRequestScope - any client getting through the TLS termination can utilise this
        call (as is intended)"""
        site_id_scope: Optional[int] = None
        if scope.source == CertificateType.DEVICE_CERTIFICATE:
            existing_device_site = await select_single_site_with_lfdi(session, scope.lfdi, scope.aggregator_id)
            if existing_device_site is None:
                return DeviceCapabilityMapper.map_to_unregistered_response(scope)
            else:
                site_id_scope = existing_device_site.site_id

        # Get all the 'Link's and 'ListLink's for a device capability response
        links = await link.get_supported_links(
            session=session,
            aggregator_id=scope.aggregator_id,
            site_id=site_id_scope,
            scope=scope,
            model=DeviceCapabilityResponse,
        )
        return DeviceCapabilityMapper.map_to_response(scope=scope, links=links)
