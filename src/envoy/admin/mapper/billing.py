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
from envoy_schema.server.schema.sep2.types import AccumulationBehaviourType, DataQualifierType, FlowDirectionType

from envoy.admin.crud.billing import BillingData
from envoy.server.mapper.common import pow10_to_decimal_value
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.log import CalculationLog
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.tariff import TariffGeneratedRate


class BillingMapper:
    @staticmethod
    def map_reading(reading: SiteReading) -> BillingReading:
        value = pow10_to_decimal_value(reading.value, reading.site_reading_type.power_of_ten_multiplier)
        if value is None:
            raise Exception(
                f"SiteReading {reading.site_reading_id} can't generate reading value value '{reading.value}'"
            )

        # If the reading is from the perspective of a client EXPORTING into the grid, we need to flip the sign
        # to align with our internal interpretation of +'ve meaning import and -'ve meaning export
        if reading.site_reading_type.flow_direction == FlowDirectionType.REVERSE:
            value = -value

        return BillingReading(
            site_id=reading.site_reading_type.site_id,
            period_start=reading.time_period_start,
            duration_seconds=reading.time_period_seconds,
            value=value,
        )

    @staticmethod
    def reading_type_to_billing_primacy(srt: SiteReadingType) -> int:
        """Given a SiteReadingType - generate a primacy (integer) that represents the 'quality' of reading type for
        use with billing data. Higher primacy indicates higher 'quality'

        Eg - MEAN Readings will be preferred over Instantaneous Readings which will be preferred over MIN/MAX readings
        """

        # Remember - Higher primacy equals higher quality
        # Accumulation Behavior is our "secondary" consideration (i.e tiebreaker)
        secondary_index = 0
        if srt.accumulation_behaviour == AccumulationBehaviourType.NOT_APPLICABLE:
            secondary_index = 0  # LOWEST PRIORITY/PRIMACY
        elif srt.accumulation_behaviour == AccumulationBehaviourType.CUMULATIVE:
            secondary_index = 1
        elif srt.accumulation_behaviour == AccumulationBehaviourType.INDICATING:
            secondary_index = 2
        elif srt.accumulation_behaviour == AccumulationBehaviourType.INSTANTANEOUS:
            secondary_index = 3
        elif srt.accumulation_behaviour == AccumulationBehaviourType.DELTA_DATA:
            secondary_index = 4
        elif srt.accumulation_behaviour == AccumulationBehaviourType.SUMMATION:
            secondary_index = 5  # HIGHEST PRIORITY/PRIMACY
        else:
            raise Exception(f"Unexpected accumulation behaviour: {srt.accumulation_behaviour}")

        primary_index = 0
        if srt.data_qualifier == DataQualifierType.NOT_APPLICABLE:
            primary_index = 100  # LOWEST PRIORITY/PRIMACY
        elif srt.data_qualifier == DataQualifierType.STANDARD:
            primary_index = 200
        elif srt.data_qualifier == DataQualifierType.STD_DEVIATION_OF_POPULATION:
            primary_index = 300
        elif srt.data_qualifier == DataQualifierType.STD_DEVIATION_OF_SAMPLE:
            primary_index = 400
        elif srt.data_qualifier == DataQualifierType.MINIMUM:
            primary_index = 500
        elif srt.data_qualifier == DataQualifierType.MAXIMUM:
            primary_index = 600
        elif srt.data_qualifier == DataQualifierType.AVERAGE:
            primary_index = 700  # HIGHEST PRIORITY/PRIMACY
        else:
            raise Exception(f"Unexpected data qualifier: {srt.data_qualifier}")

        return primary_index + secondary_index

    @staticmethod
    def choose_best_billing_readings(readings: Iterable[SiteReading]) -> list[SiteReading]:
        """Given a stream of readings that all represent the same interval/site/type, pick the subset
        of readings that represent the highest quality billing data.

        NOTE: Expects readings to all have the same site_id/timestamp/uom

        Eg - Given a set of Active Power Readings for Time X and Site Y - return the reading(s) that have the highest
        values returned by reading_type_to_billing_primacy:"""
        best_primacy = -1
        best_readings = []

        for reading in readings:
            primacy = BillingMapper.reading_type_to_billing_primacy(reading.site_reading_type)
            if primacy < best_primacy:
                continue
            elif primacy == best_primacy:
                best_readings.append(reading)
            else:
                best_readings.clear()
                best_primacy = primacy
                best_readings.append(reading)

        return best_readings

    @staticmethod
    def aggregate_readings_for_site_timestamp(readings: Iterable[SiteReading]) -> Generator[BillingReading, None, None]:
        """Given an incoming stream of readings, aggregate any readings that coincide with eachother by first filtering
        with choose_best_billing_readings and then adding their values together.

        NOTE: Expects readings to be sorted on site_id/timestamp - unsorted lists will fail to aggregate correctly

        The final result is a set of readings that have had their phasing info added together."""

        def combine_readings_to_billing_reading(readings: Iterable[SiteReading]) -> Optional[BillingReading]:
            combined_reading: Optional[BillingReading] = None
            for reading in readings:
                if combined_reading:
                    combined_reading.value += BillingMapper.map_reading(reading).value
                else:
                    combined_reading = BillingMapper.map_reading(reading)
            return combined_reading

        last_key: tuple[int, datetime] = (-1, datetime.min)
        last_key_readings: list[SiteReading] = []
        for next_reading in readings:
            next_key = (next_reading.site_reading_type.site_id, next_reading.time_period_start)

            if next_key == last_key:
                # If our key matches the previously iterated reading, we aim to roll this reading data into the
                # previous readings and then continue looking
                last_key_readings.append(next_reading)
                continue
            else:
                # In this case, we are done accumulating readings for the previous key. We can return the aggregated val
                billing_reading = combine_readings_to_billing_reading(
                    BillingMapper.choose_best_billing_readings(last_key_readings)
                )
                if billing_reading:
                    yield billing_reading

                last_key_readings.clear()
                last_key_readings.append(next_reading)
                last_key = next_key

        # once we are done - combine the remaining readings we were aggregating
        billing_reading = combine_readings_to_billing_reading(
            BillingMapper.choose_best_billing_readings(last_key_readings)
        )
        if billing_reading:
            yield billing_reading

    @staticmethod
    def map_doe(doe: DynamicOperatingEnvelope) -> BillingDoe:
        return BillingDoe(
            duration_seconds=doe.duration_seconds,
            export_limit_watts=doe.export_limit_watts if doe.export_limit_watts is not None else Decimal(0),
            import_limit_active_watts=(
                doe.import_limit_active_watts if doe.import_limit_active_watts is not None else Decimal(0)
            ),
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
