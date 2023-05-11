from envoy.server.model.site import Site
from envoy.server.schema.csip_aus.connection_point import ConnectionPointResponse


class ConnectionPointMapper:
    @staticmethod
    def map_to_response(site: Site) -> ConnectionPointResponse:
        return ConnectionPointResponse.validate(
            {
                "id": site.nmi if site.nmi else "",
            }
        )
