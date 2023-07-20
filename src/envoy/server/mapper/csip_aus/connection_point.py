from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse

from envoy.server.model.site import Site


class ConnectionPointMapper:
    @staticmethod
    def map_to_response(site: Site) -> ConnectionPointResponse:
        return ConnectionPointResponse.validate(
            {
                "id": site.nmi if site.nmi else "",
            }
        )
