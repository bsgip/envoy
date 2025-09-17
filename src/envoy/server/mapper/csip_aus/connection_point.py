from envoy_schema.server.schema import uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse

from envoy.server.mapper.common import generate_href
from envoy.server.model.site import Site
from envoy.server.request_scope import BaseRequestScope


class ConnectionPointMapper:
    @staticmethod
    def map_to_response(scope: BaseRequestScope, site: Site) -> ConnectionPointResponse:
        return ConnectionPointResponse(
            id=site.nmi if site.nmi else "", href=generate_href(uri.ConnectionPointUri, scope, site_id=site.site_id)
        )
