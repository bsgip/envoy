"""Holds all controllers/routing for incoming requests"""

from envoy.server.api.csip_aus.connection_point import router as cp_router
from envoy.server.api.sep2.der import router as der_router
from envoy.server.api.sep2.derp import router as derp_router
from envoy.server.api.sep2.device_capability import router as dcap_router
from envoy.server.api.sep2.end_device import router as edev_router
from envoy.server.api.sep2.function_set_assignments import router as fsa_router
from envoy.server.api.sep2.metering_mirror import router as mm_router
from envoy.server.api.sep2.pricing import router as price_router
from envoy.server.api.sep2.response import router as response_router
from envoy.server.api.sep2.subscription import router as sub_router
from envoy.server.api.sep2.time import router as tm_router
from envoy.server.api.unsecured.health import router as health_router
from envoy.server.api.unsecured.version import router as version_router

__all__ = ["routers"]

routers = [
    cp_router,
    dcap_router,
    edev_router,
    der_router,
    derp_router,
    fsa_router,
    mm_router,
    price_router,
    response_router,
    sub_router,
    tm_router,
]

unsecured_routers = [health_router, version_router]
