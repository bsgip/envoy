from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DynamicOperatingEnvelopeAdmin(BaseModel):
    """Stores information to populate admin db related
    to DOEs TODO"""

    dynamic_operating_envelope_id: int
    site_id: int
    changed_time: datetime
    duration_seconds: int
    import_limit_active_watts: Decimal
    export_limit_watts: Decimal
