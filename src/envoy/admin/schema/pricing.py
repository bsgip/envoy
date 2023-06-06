from datetime import datetime

from pydantic import BaseModel

from envoy.server.schema.sep2.types import CurrencyCode


class TariffRequest(BaseModel):
    """Basic attributes for the creation of a new tariff structure."""

    name: str
    dnsp_code: str
    currency_code: CurrencyCode


class TariffResponse(BaseModel):
    """Response model for Tariff including id and modification time."""

    tariff_id: int
    name: str
    dnsp_code: str
    currency_code: CurrencyCode
    changed_time: datetime


class TariffGeneratedRateRequest(BaseModel):
    """Time of use tariff pricing"""

    tariff_id: int
    site_id: int
    start_time: datetime
    duration_seconds: int
    import_active_price: float
    export_active_price: float
    import_reactive_price: float
    export_reactive_price: float
