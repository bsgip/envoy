from envoy.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


class TariffMapper:
    @staticmethod
    def map_from_request(tariff: TariffRequest) -> Tariff:
        # deviceCategory is a hex string

        return Tariff(
            tariff_id=tariff.tariff_id,
            name=tariff.name,
            changed_time=tariff.changed_time,
            currency_code=tariff.currency_code,
            dnsp_code=tariff.dnsp_code,
        )
