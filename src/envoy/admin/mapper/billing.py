from datetime import datetime
from decimal import Decimal
from typing import Generator, Iterable, Optional

from envoy_schema.admin.schema.billing import (
    AggregatorBillingResponse,
    BillingDoe,
    BillingReading,
    BillingTariffRate,
    CalculationLogBillingResponse,
    SiteBillingResponse,
)

from envoy.admin.crud.billing import BillingData
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.log import CalculationLog
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
    def aggregate_readings_for_site_timestamp(readings: Iterable[SiteReading]) -> Generator[BillingReading, None, None]:
        """Given an incoming stream of readings, aggregate any readings that coincide with eachother by adding them.

        NOTE: Expects readings to be sorted on site_id/timestamp - unsorted lists will fail to aggregate correctly

        The final result is a set of readings that have had their phasing info added together"""

        last_key: tuple[int, datetime] = (-1, datetime.min)
        last_reading: Optional[BillingReading] = None
        for next_reading in readings:
            next_key = (next_reading.site_reading_type.site_id, next_reading.time_period_start)
            mapped_next_reading = BillingMapper.map_reading(next_reading)

            if next_key == last_key:
                # If our key matches the previously iterated reading, we roll this reading data into the previous value
                # and then continue looking
                if last_reading is None:
                    raise Exception(f"key {next_key} matched {last_key} but last_reading is None.")  # Shouldn't happen

                last_reading.value += mapped_next_reading.value
                continue
            else:
                # In this case, we are done rolling values into the previous value and can return it
                if last_reading is not None:
                    yield last_reading

                last_reading = mapped_next_reading
                last_key = next_key

        # once we are done - return the last reading we were aggregating
        if last_reading is not None:
            yield last_reading

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
    def map_to_aggregator_response(
        aggregator: Aggregator, tariff_id: int, period_start: datetime, period_end: datetime, data: BillingData
    ) -> AggregatorBillingResponse:
        return AggregatorBillingResponse(
            aggregator_id=aggregator.aggregator_id,
            aggregator_name=aggregator.name,
            period_start=period_start,
            period_end=period_end,
            tariff_id=tariff_id,
            varh_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.varh_readings)),
            wh_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.wh_readings)),
            watt_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.watt_readings)),
            active_does=[BillingMapper.map_doe(d) for d in data.active_does],
            active_tariffs=[BillingMapper.map_rate(r) for r in data.active_tariffs],
        )

    @staticmethod
    def map_to_sites_response(
        site_ids: list[int], tariff_id: int, period_start: datetime, period_end: datetime, data: BillingData
    ) -> SiteBillingResponse:
        return SiteBillingResponse(
            site_ids=site_ids,
            period_start=period_start,
            period_end=period_end,
            tariff_id=tariff_id,
            varh_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.varh_readings)),
            wh_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.wh_readings)),
            watt_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.watt_readings)),
            active_does=[BillingMapper.map_doe(d) for d in data.active_does],
            active_tariffs=[BillingMapper.map_rate(r) for r in data.active_tariffs],
        )

    @staticmethod
    def map_to_calculation_log_response(
        calculation_log: CalculationLog, tariff_id: int, data: BillingData
    ) -> CalculationLogBillingResponse:
        return CalculationLogBillingResponse(
            calculation_log_id=calculation_log.calculation_log_id,
            tariff_id=tariff_id,
            varh_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.varh_readings)),
            wh_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.wh_readings)),
            watt_readings=list(BillingMapper.aggregate_readings_for_site_timestamp(data.watt_readings)),
            active_does=[BillingMapper.map_doe(d) for d in data.active_does],
            active_tariffs=[BillingMapper.map_rate(r) for r in data.active_tariffs],
        )
