from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BillingReading(BaseModel):
    site_id: int
    period_start: datetime
    duration_seconds: int
    value: Decimal  # Positive indicates import, negative indicates export


class BillingTariffRate(BaseModel):
    site_id: int
    period_start: datetime
    duration_seconds: int
    import_active_price: Decimal
    export_active_price: Decimal
    import_reactive_price: Decimal
    export_reactive_price: Decimal


class BillingDoe(BaseModel):
    site_id: int
    period_start: datetime
    duration_seconds: int
    import_limit_active_watts: Decimal
    export_limit_watts: Decimal


class BillingResponse(BaseModel):
    """Response model for a billing report"""

    aggregator_id: int
    aggregator_name: str
    period_start: datetime
    period_end: datetime
    tariff_id: int

    varh_readings: list[BillingReading]  # Will be ordered by site_id then period_start
    wh_readings: list[BillingReading]  # Will be ordered by site_id then period_start
    active_tariffs: list[BillingTariffRate]  # Will be ordered by site_id then period_start
    active_does: list[BillingDoe]  # Will be ordered by site_id then period_start
