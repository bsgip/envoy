from datetime import datetime

from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.end_device import select_aggregator_site_count, select_single_site_with_lfdi
from envoy.server.crud.site_reading import count_site_reading_types_for_aggregator  # is this mup?
from envoy.server.manager.server import RuntimeServerConfigManager
from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.request_scope import CertificateType, UnregisteredRequestScope


class DeviceCapabilityManager:
    @staticmethod
    async def fetch_device_capability(
        session: AsyncSession, scope: UnregisteredRequestScope
    ) -> DeviceCapabilityResponse:
        """Noting this operates on a RawRequestScope - any client getting through the TLS termination can utilise this
        call (as is intended)"""
        edev_cnt: int
        mup_cnt: int

        # Aggregator certs need to be treated differently from device certs
        if scope.source == CertificateType.DEVICE_CERTIFICATE:
            existing_device_site = await select_single_site_with_lfdi(session, scope.lfdi, scope.aggregator_id)
            if existing_device_site is None:
                return DeviceCapabilityMapper.map_to_unregistered_response(scope=scope)
            else:
                edev_cnt = 1
                mup_cnt = await count_site_reading_types_for_aggregator(
                    session, scope.aggregator_id, existing_device_site.site_id, datetime.min
                )
        else:
            # Aggregator certificate
            edev_cnt = await select_aggregator_site_count(session, scope.aggregator_id, datetime.min)
            edev_cnt += 1  # Adjust the count to include the virtual aggregator end device at "edev/0"
            mup_cnt = await count_site_reading_types_for_aggregator(session, scope.aggregator_id, None, datetime.min)

        # fetch runtime server config
        config = await RuntimeServerConfigManager.fetch_current_config(session)

        return DeviceCapabilityMapper.map_to_response(
            scope=scope, edev_cnt=edev_cnt, mup_cnt=mup_cnt, pollrate_seconds=config.dcap_pollrate_seconds
        )
