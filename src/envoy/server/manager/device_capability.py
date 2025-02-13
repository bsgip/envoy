from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.end_device import select_single_site_with_lfdi, select_aggregator_site_count
from envoy.server.crud.site_reading import count_site_reading_types_for_aggregator  # is this mup?
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
                return DeviceCapabilityMapper.map_to_unregistered_response(scope=scope)
            else:
                site_id_scope = existing_device_site.site_id

        # Get all counts needed to form the 'Link's and 'ListLink's in a device capability response (registered)
        edev_cnt = await select_aggregator_site_count(session, scope.aggregator_id, datetime.min)
        mup_cnt = await count_site_reading_types_for_aggregator(
            session, scope.aggregator_id, site_id_scope, datetime.min
        )
        return DeviceCapabilityMapper.map_to_response(scope=scope, edev_cnt=edev_cnt, mup_cnt=mup_cnt)
