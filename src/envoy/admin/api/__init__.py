"""Holds all controllers/routing for incoming requests"""

from envoy.admin.api.doe import router as doe_router
from envoy.admin.api.pricing import router as price_router
from envoy.admin.api.site import router as site_router

routers = [doe_router, price_router, site_router]
