
from datetime import date, time
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.schema.sep2.metering import ConsumptionBlockType
from envoy.server.schema.sep2.pricing import ConsumptionTariffIntervalListResponse


class RateComponentManager:
    @staticmethod
    def parse_rate_component_id(id: str) -> date:
        """Validates that id looks like YYYY-MM-DD. Returns parsed date object if it does
        otherwise raises InvalidMappingError"""
        if len(id) != 10 or id[4] != '-' or id[7] != '-':
            raise InvalidMappingError(f"Expected YYYY-MM-DD for time_tariff_interval_id but got {id}")


class TimeTariffIntervalManager:
    @staticmethod
    def parse_time_tariff_interval_id(id: str) -> time:
        """Validates that id looks like HH:MM. Returns parsed time object if it does
        otherwise raises InvalidMappingError"""
        try:
            return time.fromisoformat(id)
        except ValueError:
            raise InvalidMappingError(f"Expected HH:MM for time_tariff_interval_id but got {id}")


class ConsumptionTariffIntervalManager:
    # /tp/{tariff_id}/rc/{rate_component_id}/tti/{tti_id}/cti/{price}
    @staticmethod
    def _generate_href(tariff_id: int, rate_component_id: str, time_tariff_interval: str, price: int):
        return f"/tp/{tariff_id}/rc/{quote(rate_component_id)}/tti/{quote(time_tariff_interval)}/cti/{price}/"

    @staticmethod
    async def fetch_consumption_tariff_interval_list(tariff_id: int,
                                                     rate_component_id: str,
                                                     time_tariff_interval: str,
                                                     price: int) -> ConsumptionTariffIntervalListResponse:
        """This is a fully virtualised entity 'lookup' that doesn't require interaction with the DB"""
        href = ConsumptionTariffIntervalManager._generate_href(
            tariff_id,
            rate_component_id,
            time_tariff_interval,
            price)
        return ConsumptionTariffIntervalListResponse.validate({
            "all_": 1,
            "results": 1,
            "ConsumptionTariffInterval": [{
                "href": href,
                "consumptionBlock": ConsumptionBlockType.NOT_APPLICABLE,
                "price": price,
                "startValue": 0
            }]
        })
