from datetime import datetime, timedelta
from typing import List, Optional

from envoy_schema.admin.schema.pricing import (
    TariffComponentRequest,
    TariffComponentResponse,
    TariffGeneratedRateRequest,
    TariffRequest,
    TariffResponse,
)

from envoy.server.exception import InvalidMappingError
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate


class TariffMapper:
    @staticmethod
    def map_from_request(changed_time: datetime, tariff: TariffRequest) -> Tariff:
        return Tariff(
            name=tariff.name,
            changed_time=changed_time,
            currency_code=tariff.currency_code,
            dnsp_code=tariff.dnsp_code,
            fsa_id=tariff.fsa_id,
            price_power_of_ten_multiplier=tariff.price_power_of_ten_multiplier,
            primacy=tariff.primacy,
        )

    @staticmethod
    def map_to_response(tariff: Tariff) -> TariffResponse:
        return TariffResponse(
            tariff_id=tariff.tariff_id,
            created_time=tariff.created_time,
            changed_time=tariff.changed_time,
            dnsp_code=tariff.dnsp_code,
            currency_code=tariff.currency_code,
            name=tariff.name,
            fsa_id=tariff.fsa_id,
            price_power_of_ten_multiplier=(
                tariff.price_power_of_ten_multiplier if tariff.price_power_of_ten_multiplier else 0
            ),
            primacy=tariff.primacy,
        )


class TariffComponentMapper:
    @staticmethod
    def map_from_request(changed_time: datetime, tc: TariffComponentRequest) -> TariffComponent:
        return TariffComponent(
            changed_time=changed_time,
            tariff_id=tc.tariff_id,
            role_flags=tc.role_flags,
            description=tc.description,
            accumulation_behaviour=tc.accumulation_behaviour,
            commodity=tc.commodity,
            data_qualifier=tc.data_qualifier,
            flow_direction=tc.flow_direction,
            kind=tc.kind,
            phase=tc.phase,
            power_of_ten_multiplier=tc.power_of_ten_multiplier,
            uom=tc.uom,
        )

    @staticmethod
    def map_to_response(tc: TariffComponent) -> TariffComponentResponse:
        return TariffComponentResponse(
            tariff_component_id=tc.tariff_component_id,
            created_time=tc.created_time,
            changed_time=tc.changed_time,
            tariff_id=tc.tariff_id,
            role_flags=tc.role_flags,
            description=tc.description,
            accumulation_behaviour=tc.accumulation_behaviour,
            commodity=tc.commodity,
            data_qualifier=tc.data_qualifier,
            flow_direction=tc.flow_direction,
            kind=tc.kind,
            phase=tc.phase,
            power_of_ten_multiplier=tc.power_of_ten_multiplier,
            uom=tc.uom,
        )


class TariffGeneratedRateListMapper:

    @staticmethod
    def map_from_single_rate_request(
        changed_time: datetime, rate: TariffGeneratedRateRequest, tariff_id: Optional[int]
    ) -> TariffGeneratedRate:
        if tariff_id is None:
            raise InvalidMappingError(f"Unable to identify Tariff id for TariffComponent {rate.tariff_component_id}")

        end_time = rate.start_time + timedelta(seconds=rate.duration_seconds)

        return TariffGeneratedRate(
            tariff_id=tariff_id,
            tariff_component_id=rate.tariff_component_id,
            site_id=rate.site_id,
            calculation_log_id=rate.calculation_log_id,
            changed_time=changed_time,
            start_time=rate.start_time,
            duration_seconds=rate.duration_seconds,
            end_time=end_time,
            price_pow10_encoded=rate.price_pow10_encoded,
            block_1_start_pow10_encoded=rate.block_1_start_pow10_encoded,
            price_pow10_encoded_block_1=rate.price_pow10_encoded_block_1,
        )

    @staticmethod
    def map_from_request(
        changed_time: datetime,
        tariff_genrate_list: List[TariffGeneratedRateRequest],
        tariff_ids_by_component_id: dict[int, int],
    ) -> List[TariffGeneratedRate]:
        return [
            TariffGeneratedRateListMapper.map_from_single_rate_request(
                changed_time, tariff_genrate, tariff_ids_by_component_id.get(tariff_genrate.tariff_component_id, None)
            )
            for tariff_genrate in tariff_genrate_list
        ]
