import pytest
from fastapi import APIRouter, FastAPI
from envoy.server.endpoint_exclusion import (
    ExcludeEndpointException,
    generate_routers_with_excluded_endpoints,
    HTTPMethod,
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
    assert filtered_routers[0].routes[0].path == "/somepath"
    assert filtered_routers[0].routes[0].methods == {"GET", "HEAD"}


def test_generate_routers_with_excluded_endpoints_single_method():
    """Tests Disabling one method from a route with multiple methods"""
    # Arrange
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD, HTTPMethod.DELETE])

    # Act
    filtered_routers = generate_routers_with_excluded_endpoints([router], {("DELETE", "/somepath")})

    # Assert
    assert len(filtered_routers[0].routes) == 1
    assert filtered_routers[0].routes[0].path == "/somepath"
    assert filtered_routers[0].routes[0].methods == {"GET", "HEAD"}


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
    assert router.routes[0].path == "/somepath"
    assert router.routes[0].methods == {"GET", "HEAD"}


def test_generate_routers_with_excluded_endpoints_raises_error_no_side_effects():
    """Should raise error on unmatched endpoint, without side-effects"""
    # Arrange
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD])

    # Act / Assert
    with pytest.raises(ExcludeEndpointException):
        generate_routers_with_excluded_endpoints([router], {("HEAD", "/somepath"), ("GET", "/someotherepath")})

    # Assert
    assert len(router.routes) == 1
    assert router.routes[0].path == "/somepath"
    assert router.routes[0].methods == {"GET", "HEAD"}


def test_generate_routers_with_excluded_endpoints_includes_successfully():
    """Tests no errors raised when modified router is added to app"""
    # Arrange
    app = FastAPI()
    router = APIRouter()
    router.add_api_route("/somepath", lambda x: x, methods=[HTTPMethod.GET, HTTPMethod.HEAD])

    # Act
    filtered_routers = generate_routers_with_excluded_endpoints([router], {("HEAD", "/somepath")})
    app.include_router(filtered_routers[0])

    # Assert
    route = [r for r in app.routes if r.path == "/somepath"].pop()
    assert route.methods == {"GET"}
