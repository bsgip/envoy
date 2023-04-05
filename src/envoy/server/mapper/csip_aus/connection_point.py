
from envoy.server.model.site import Site
from envoy.server.schema.csip_aus.connection_point import ConnectionPoint


class ConnectionPointMapper:
    @staticmethod
    def map_to_response(site: Site) -> ConnectionPoint:
        return ConnectionPoint.validate(
            {
                "id": site.nmi if site.nmi else '',
            }
        )
