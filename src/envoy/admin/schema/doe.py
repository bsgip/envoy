from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DynamicOperatingEnvelopeRequest(BaseModel):
    """Dynamic Operating Envelope basic model"""

    site_id: int
    duration_seconds: int
    import_limit_active_watts: Decimal
    export_limit_watts: Decimal
    start_time: datetime
