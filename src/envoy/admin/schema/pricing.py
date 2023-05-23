from datetime import datetime

from pydantic import BaseModel

from envoy.server.schema.sep2.types import CurrencyCode


class TariffRequest(BaseModel):
    """TODO"""

    # tariff_generated_rate
    tariff_generated_rate_id: int
    site_id: int
    duration_seconds: int
    import_active_price: float
    export_active_price: float
    import_reactive_price: float
    export_reactive_price: float

    # tariff
    tariff_id: int
    name: str
    dsnp_code: str
    currency_code: CurrencyCode
    changed_time: datetime
