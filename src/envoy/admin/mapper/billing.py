from datetime import datetime
from decimal import Decimal

from envoy_schema.admin.schema.billing import BillingDoe, BillingReading, BillingResponse, BillingTariffRate

from envoy.admin.crud.billing import BillingData
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.tariff import TariffGeneratedRate


class BillingMapper:
    @staticmethod
    def map_reading(reading: SiteReading) -> BillingReading:
        power = Decimal("10") ** -reading.site_reading_type.power_of_ten_multiplier
        value = Decimal(reading.value) * power
        return BillingReading(
            site_id=reading.site_reading_type.site_id,
            period_start=reading.time_period_start,
            duration_seconds=reading.time_period_seconds,
            value=value,
        )

    @staticmethod
    def map_doe(doe: DynamicOperatingEnvelope) -> BillingDoe:
        return BillingDoe(
            duration_seconds=doe.duration_seconds,
            export_limit_watts=doe.export_limit_watts,
            import_limit_active_watts=doe.import_limit_active_watts,
            period_start=doe.start_time,
            site_id=doe.site_id,
        )

    @staticmethod
    def map_rate(r: TariffGeneratedRate) -> BillingTariffRate:
        return BillingTariffRate(
            duration_seconds=r.duration_seconds,
            site_id=r.site_id,
            export_active_price=r.export_active_price,
            export_reactive_price=r.export_reactive_price,
            import_active_price=r.import_active_price,
            import_reactive_price=r.import_reactive_price,
            period_start=r.start_time,
        )

    @staticmethod
    def map_to_response(
        aggregator: Aggregator, tariff_id: int, period_start: datetime, period_end: datetime, data: BillingData
    ) -> BillingResponse:
        return BillingResponse(
            aggregator_id=aggregator.aggregator_id,
            aggregator_name=aggregator.name,
            period_start=period_start,
            period_end=period_end,
            tariff_id=tariff_id,
            varh_readings=[BillingMapper.map_reading(r) for r in data.varh_readings],
            wh_readings=[BillingMapper.map_reading(r) for r in data.wh_readings],
            active_does=[BillingMapper.map_doe(d) for d in data.active_does],
            active_tariffs=[BillingMapper.map_rate(r) for r in data.active_tariffs],
        )
