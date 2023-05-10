"""Holds all controllers/routing for incoming requests"""

from envoy.server.api.csip_aus.connection_point import router as cp_router
from envoy.server.api.sep2.device_capability import router as dcap_router
from envoy.server.api.sep2.end_device import router as edev_router
from envoy.server.api.sep2.function_set_assignments import router as fsa_router
from envoy.server.api.sep2.pricing import router as price_router
from envoy.server.api.sep2.time import router as tm_router

__all__ = ["routers"]

routers = [cp_router, dcap_router, edev_router, fsa_router, price_router, tm_router]
