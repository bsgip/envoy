from copy import deepcopy
from enum import Enum
import logging

from starlette.routing import BaseRoute, Route
from fastapi import APIRouter


logging.basicConfig(style="{", level=logging.INFO)
logger = logging.getLogger(__name__)


# This should be replaced with http.HTTPMethod when this project is ported to Python 3.11
class HTTPMethod(str, Enum):
    DELETE = "DELETE"
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PATCH = "PATCH"
    PUT = "PUT"


class ExcludeEndpointException(Exception): ...  # noqa: E701


EndpointExclusionSet = set[tuple[HTTPMethod, str]]


def generate_routers_with_excluded_endpoints(
    api_routers: list[APIRouter], exclude_endpoints: EndpointExclusionSet
) -> list[APIRouter]:
    """Generates a new list of api routers with endpoint filters applied. Endpoint filters are defined as tuple
    of HTTPMethod and URI string). A route is removed entirely if all it's available methods are removed. Validates all
    endpoints before modifying routers.

    NOTE: This function should be called before routers are included in the FastAPI app. The assumption is that FastAPI
    defers route registration and schema generation until routers are included. If this changes and internal state is
    managed during APIRouter setup, this approach may need to be revisited.

    Raises:
        ExcludeEndpointException: if any endpoints cannot be found across the given routers
    """

    logger.info(f"Disabling the following endpoints from routers: {exclude_endpoints}")

    # We deepcopy and mutate to avoid reconstruction (where we may miss metadata), should be safe.
    routers = deepcopy(api_routers)
    endpoint_filters = deepcopy(exclude_endpoints)

    for router in routers:
        remaining_routes: list[BaseRoute] = []
        for route in router.routes:
            if isinstance(route, Route) and route.methods:
                remaining_methods: list[str] = []

                # filtering route methods
                for method in route.methods:
                    endpoint = (HTTPMethod(method), route.path)
                    if endpoint in endpoint_filters:
                        endpoint_filters.discard(endpoint)  # tracking which filters have been applied.
                    else:
                        remaining_methods.append(method)

                # mutating route methods
                route.methods = set(remaining_methods)
                if route.methods:
                    remaining_routes.append(route)
        router.routes = remaining_routes

    if endpoint_filters:
        raise ExcludeEndpointException(
            f"The following endpoints cannot be found in provided routers: {endpoint_filters}"
        )
    return routers
