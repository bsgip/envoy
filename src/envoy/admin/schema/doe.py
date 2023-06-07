from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from envoy.server.model import Site


class DynamicOperatingEnvelopeAdminRequest(BaseModel):
    """TODO"""

    site_id: int
    duration_seconds: int
    import_limit_active_watts: Decimal
    export_limit_watts: Decimal


class DynamicOperatingEnvelopeAdminResponse(BaseModel):
    """Stores information to populate admin db related
    to DOEs TODO"""

    dynamic_operating_envelope_id: int
    site_id: int
    site: Site
    changed_time: datetime
    duration_seconds: int
    import_limit_active_watts: Decimal
    export_limit_watts: Decimal

    class Config:
        arbitrary_types_allowed = True
