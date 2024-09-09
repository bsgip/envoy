from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud import link
from envoy.server.mapper.sep2.device_capability import DeviceCapabilityMapper
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID
from envoy.server.request_scope import RawRequestScope


class DeviceCapabilityManager:
    @staticmethod
    async def fetch_device_capability(session: AsyncSession, scope: RawRequestScope) -> DeviceCapabilityResponse:
        """Noting this operates on a RawRequestScope - any client getting through the TLS termination can utilise this
        call (as is intended)"""
        agg_id = scope.aggregator_id
        if agg_id is None:
            if scope.site_id is None:
                return DeviceCapabilityMapper.map_to_unregistered_response(scope)
            else:
                agg_id = NULL_AGGREGATOR_ID

        # Get all the 'Link's and 'ListLink's for a device capability response
        links = await link.get_supported_links(
            session=session,
            aggregator_id=agg_id,
            site_id=scope.site_id,
            scope=scope,
            model=DeviceCapabilityResponse,
        )
        return DeviceCapabilityMapper.map_to_response(scope=scope, links=links)
