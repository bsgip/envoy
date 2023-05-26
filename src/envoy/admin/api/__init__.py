"""Holds all controllers/routing for incoming requests"""

from envoy.admin.api.pricing import router as price_router

__all__ = ["routers"]

routers = [price_router]
