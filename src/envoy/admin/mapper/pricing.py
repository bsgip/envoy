from datetime import datetime
from zoneinfo import ZoneInfo

from envoy.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest, TariffResponse
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


class TariffMapper:
    @staticmethod
    def map_from_request(tariff: TariffRequest) -> Tariff:
        return Tariff(
            tariff_id=tariff.tariff_id,
            name=tariff.name,
            changed_time=datetime.now(tz=ZoneInfo("UTC")),
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
