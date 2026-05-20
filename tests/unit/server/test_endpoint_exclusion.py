import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from envoy.server.endpoint_exclusion import (
    ExcludeEndpointException,
    HTTPMethod,
    generate_routers_with_excluded_endpoints,
)


def test_generate_routers_with_excluded_endpoints():
    """Basic success test"""
    # Arrange
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD])
    router.add_api_route("/someotherpath", lambda x: x, methods=[HTTPMethod.DELETE])

    # Act
    filtered_routers = generate_routers_with_excluded_endpoints([router], {(HTTPMethod.DELETE, "/someotherpath")})

    # Assert
    assert len(filtered_routers[0].routes) == 1
    route0 = filtered_routers[0].routes[0]
    assert isinstance(route0, APIRoute)
    assert route0.path == "/somepath"
    assert route0.methods == {"GET", "HEAD"}


def test_generate_routers_with_excluded_endpoints_single_method():
    """Tests Disabling one method from a route with multiple methods"""
    # Arrange
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD, HTTPMethod.DELETE])

    # Act
    filtered_routers = generate_routers_with_excluded_endpoints([router], {(HTTPMethod.DELETE, "/somepath")})

    # Assert
    assert len(filtered_routers[0].routes) == 1
    route0 = filtered_routers[0].routes[0]
    assert isinstance(route0, APIRoute)
    assert route0.path == "/somepath"
    assert route0.methods == {"GET", "HEAD"}


def test_generate_routers_with_excluded_endpoints_raises_error_on_unmatched_endpoint():
    """Should raise error on unmatched endpoint"""
    # Arrange
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD])

    # Act / Assert
    with pytest.raises(ExcludeEndpointException):
        generate_routers_with_excluded_endpoints([router], {(HTTPMethod.DELETE, "/sometherepath")})

    # Assert
    assert len(router.routes) == 1
    route0 = router.routes[0]
    assert isinstance(route0, APIRoute)
    assert route0.path == "/somepath"
    assert route0.methods == {"GET", "HEAD"}


def test_generate_routers_with_excluded_endpoints_raises_error_no_side_effects():
    """Should raise error on unmatched endpoint, without side-effects"""
    # Arrange
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD])

    # Act / Assert
    with pytest.raises(ExcludeEndpointException):
        generate_routers_with_excluded_endpoints(
            [router], {(HTTPMethod.HEAD, "/somepath"), (HTTPMethod.GET, "/someotherepath")}
        )

    # Assert
    assert len(router.routes) == 1
    route0 = router.routes[0]
    assert isinstance(route0, APIRoute)
    assert route0.path == "/somepath"
    assert route0.methods == {"GET", "HEAD"}


def test_generate_routers_with_excluded_endpoints_includes_successfully():
    """Tests no errors raised when modified router is added to app"""
    # Arrange
    app = FastAPI()
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD])

    # Act
    filtered_routers = generate_routers_with_excluded_endpoints([router], {(HTTPMethod.HEAD, "/somepath")})
    app.include_router(filtered_routers[0])

    # Assert
    api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
    route = next(r for r in api_routes if r.path == "/somepath")
    assert route.methods == {"GET"}
