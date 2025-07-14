"""Holds all controllers/routing for incoming requests"""

from envoy.admin.api.aggregator import router as aggregator_router
from envoy.admin.api.archive import router as archive_router
from envoy.admin.api.billing import router as billing_router
from envoy.admin.api.certificate import router as certificate_router
from envoy.admin.api.config import router as config_router
from envoy.admin.api.doe import router as doe_router
from envoy.admin.api.log import router as log_router
from envoy.admin.api.pricing import router as price_router
from envoy.admin.api.site import router as site_router
from envoy.admin.api.site_control import router as site_control_router
from envoy.admin.api.site_reading import router as site_reading_router

routers = [
    site_control_router,
    doe_router,
    price_router,
    site_router,
    billing_router,
    log_router,
    archive_router,
    config_router,
    aggregator_router,
    site_reading_router,
    certificate_router,
]
