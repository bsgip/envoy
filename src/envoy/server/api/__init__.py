"""Holds all controllers/routing for incoming requests"""

from envoy.server.api.sep2.time import router as tm_router

__all__ = ["routers"]

routers = [tm_router]
