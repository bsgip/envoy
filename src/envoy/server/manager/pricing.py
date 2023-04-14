
from datetime import date, time
from urllib.parse import quote

from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.schema.sep2.metering import ConsumptionBlockType
from envoy.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    TimeTariffIntervalListResponse,
)


class RateComponentManager:
    @staticmethod
    def parse_rate_component_id(id: str) -> date:
        """Validates that id looks like YYYY-MM-DD. Returns parsed date object if it does
        otherwise raises InvalidMappingError"""
        try:
            return date.fromisoformat(id)
        except ValueError:
            raise InvalidMappingError(f"Expected YYYY-MM-DD for rate_component_id but got {id}")


class TimeTariffIntervalManager:
    @staticmethod
    def parse_time_tariff_interval_id(id: str) -> time:
        """Validates that id looks like HH:MM. Returns parsed time object if it does
        otherwise raises InvalidMappingError"""
        try:
            return time.fromisoformat(id)
        except ValueError:
            raise InvalidMappingError(f"Expected HH:MM for time_tariff_interval_id but got {id}")

    @staticmethod
    async def fetch_time_tariff_interval_list(aggregator_id: int,
                                              tariff_id: int,
                                              site_id: int,
                                              rate_component_id: str,
                                              start: int,
                                              after: int,
                                              limit: int) -> TimeTariffIntervalListResponse:
        """Fetches a page of TimeTariffInterval entities and returns them in a list response"""
        raise NotImplementedError()


class ConsumptionTariffIntervalManager:
    @staticmethod
    def _generate_href(tariff_id: int, rate_component_id: str, time_tariff_interval: str, price: int):
        return f"/tp/{tariff_id}/rc/{quote(rate_component_id)}/tti/{quote(time_tariff_interval)}/cti/{price}/"

    @staticmethod
    async def fetch_consumption_tariff_interval_list(session: AsyncSession,
                                                     aggregator_id: int,
                                                     tariff_id: int,
                                                     site_id: int,
                                                     rate_component_id: str,
                                                     time_tariff_interval: str,
                                                     price: int) -> ConsumptionTariffIntervalListResponse:
        """This is a fully virtualised entity 'lookup' that doesn't require interaction with the DB

        rate_component_id and time_tariff_interval will be validated. raising InvalidMappingError if invalid"""

        # Validate ids
        RateComponentManager.parse_rate_component_id(rate_component_id)
        TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        # Validate access to site_id by aggregator_id
        if (await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)) is None:
            raise NoResultFound(f"site_id {site_id} is not accessible / does not exist")

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

    @staticmethod
    async def fetch_consumption_tariff_interval(session: AsyncSession,
                                                aggregator_id: int,
                                                tariff_id: int,
                                                site_id: int,
                                                rate_component_id: str,
                                                time_tariff_interval: str,
                                                price: int) -> ConsumptionTariffIntervalResponse:
        """This is a fully virtualised entity 'lookup' that doesn't require interaction with the DB

        rate_component_id and time_tariff_interval will be validated. raising InvalidMappingError if invalid"""

        # Validate ids
        RateComponentManager.parse_rate_component_id(rate_component_id)
        TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        # Validate access to site_id by aggregator_id
        if (await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)) is None:
            raise NoResultFound(f"site_id {site_id} is not accessible / does not exist")

        href = ConsumptionTariffIntervalManager._generate_href(
            tariff_id,
            rate_component_id,
            time_tariff_interval,
            price)
        return ConsumptionTariffIntervalResponse.validate({
            "href": href,
            "consumptionBlock": ConsumptionBlockType.NOT_APPLICABLE,
            "price": price,
            "startValue": 0
        })
