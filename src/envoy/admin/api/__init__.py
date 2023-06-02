"""Holds all controllers/routing for incoming requests"""

from envoy.admin.api.doe import router as doe_router
from envoy.admin.api.pricing import router as price_router

routers = [price_router, doe_router]
