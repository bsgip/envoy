"""Holds all controllers/routing for incoming requests"""

from envoy.server.api.sep2.end_device import router as edev_router
from envoy.server.api.sep2.time import router as tm_router

__all__ = ["routers"]

routers = [edev_router, tm_router]
