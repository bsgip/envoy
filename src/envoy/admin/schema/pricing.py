from datetime import datetime

from pydantic import BaseModel

from envoy.server.schema.sep2.types import CurrencyCode


class TariffRequest(BaseModel):
    """TODO"""

    name: str
    dnsp_code: str
    currency_code: CurrencyCode


class TariffResponse(BaseModel):
    """TODO"""

    tariff_id: int
    name: str
    dnsp_code: str
    currency_code: CurrencyCode
    changed_time: datetime


class TariffGeneratedRateRequest(BaseModel):
    """TODO"""

    tariff_id: int
    site_id: int
    start_time: datetime
    duration_seconds: int
    import_active_price: float
    export_active_price: float
    import_reactive_price: float
    export_reactive_price: float


class TariffGeneratedRateResponse(BaseModel):
    """TODO"""

    tariff_generated_rate_id: int
    changed_time: datetime
    tariff_id: int
    site_id: int
    start_time: datetime
    duration_seconds: int
    import_active_price: float
    export_active_price: float
    import_reactive_price: float
    export_reactive_price: float
