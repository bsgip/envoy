from datetime import datetime
from typing import List

from envoy_schema.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest, TariffResponse

from envoy.server.model.tariff import Tariff, TariffGeneratedRate


class TariffMapper:
    @staticmethod
    def map_from_request(changed_time: datetime, tariff: TariffRequest) -> Tariff:
        return Tariff(
            name=tariff.name,
            changed_time=changed_time,
            currency_code=tariff.currency_code,
            dnsp_code=tariff.dnsp_code,
        )

    @staticmethod
    def map_to_response(tariff: Tariff) -> TariffResponse:
        return TariffResponse(
            tariff_id=tariff.tariff_id,
            changed_time=tariff.changed_time,
            dnsp_code=tariff.dnsp_code,
            currency_code=tariff.currency_code,
            name=tariff.name,
        )


class TariffGeneratedRateListMapper:
    @staticmethod
    def map_from_request(
        changed_time: datetime, tariff_genrate_list: List[TariffGeneratedRateRequest]
    ) -> List[TariffGeneratedRate]:
        return [
            TariffGeneratedRate(
                tariff_id=tariff_genrate.tariff_id,
                site_id=tariff_genrate.site_id,
                changed_time=changed_time,
                start_time=tariff_genrate.start_time,
                duration_seconds=tariff_genrate.duration_seconds,
                import_active_price=tariff_genrate.import_active_price,
                export_active_price=tariff_genrate.export_active_price,
                import_reactive_price=tariff_genrate.import_reactive_price,
                export_reactive_price=tariff_genrate.export_reactive_price,
            )
            for tariff_genrate in tariff_genrate_list
        ]
