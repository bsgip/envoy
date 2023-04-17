
from datetime import date, datetime, time
from typing import Optional
from urllib.parse import quote

from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.crud.pricing import (
    TariffGeneratedRateDailyStats,
    count_tariff_rates_for_day,
    select_rate_daily_stats,
    select_rate_stats,
    select_tariff_rate_for_day_time,
    select_tariff_rates_for_day,
)
from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.mapper.sep2.pricing import (
    TOTAL_PRICING_READING_TYPES,
    PricingReadingType,
    RateComponentMapper,
    TariffProfileMapper,
    TimeTariffIntervalMapper,
)
from envoy.server.schema.sep2.metering import ConsumptionBlockType
from envoy.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
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

    @staticmethod
    async def fetch_rate_component_list(session: AsyncSession, aggregator_id: int, tariff_id: int, site_id: int,
                                        start: int, changed_after: datetime, limit: int) -> RateComponentListResponse:
        """RateComponent is a fully virtual entity - it has no corresponding model in our DB - it's essentialy
        just a placeholder for date + price type filtering. This function will emulate pagination by taking the
        dates with rates and then virtually expanding the page to account for iterating the various pricing readings"""

        # From the client's perspective there is a rate component for every PricingReadingType. From our perspective
        # we are just enumerating on the underlying date which means our pagination needs to be adjusted by
        # the constant TOTAL_PRICING_READING_TYPES. There's a bit of shenanigans to get it going

        db_adjusted_start = start // TOTAL_PRICING_READING_TYPES
        db_adjusted_start_remainder = start % TOTAL_PRICING_READING_TYPES
        db_adjusted_limit = (db_adjusted_start_remainder + limit) // TOTAL_PRICING_READING_TYPES
        db_adjusted_limit_remainder = (db_adjusted_start_remainder + limit) % TOTAL_PRICING_READING_TYPES
        if db_adjusted_limit_remainder > 0:
            db_adjusted_limit = db_adjusted_limit + 1

        # query for the raw underlying stats broken down by date
        rate_stats: TariffGeneratedRateDailyStats = await select_rate_daily_stats(session,
                                                                                  aggregator_id,
                                                                                  tariff_id,
                                                                                  site_id,
                                                                                  db_adjusted_start,
                                                                                  changed_after,
                                                                                  db_adjusted_limit)

        # If we are starting from a value that doesn't align with a multiple of TOTAL_PRICING_READING_TYPES we will
        # need to cull those entries that exist before our real start value
        leading_items_to_remove = db_adjusted_start_remainder

        # if the client limit could actually "bite" we need to consider culling items off the end of the list
        # to respect it
        trailing_items_to_remove = 0
        if (limit + leading_items_to_remove) < (len(rate_stats.single_date_counts) * TOTAL_PRICING_READING_TYPES):
            trailing_items_to_remove = (TOTAL_PRICING_READING_TYPES - db_adjusted_limit_remainder) % TOTAL_PRICING_READING_TYPES  # noqa e501

        return RateComponentMapper.map_to_list_response(rate_stats, leading_items_to_remove, trailing_items_to_remove,
                                                        tariff_id, site_id)


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
    async def fetch_time_tariff_interval_list(session: AsyncSession,
                                              aggregator_id: int,
                                              tariff_id: int,
                                              site_id: int,
                                              rate_component_id: str,
                                              pricing_type: PricingReadingType,
                                              start: int,
                                              after: datetime,
                                              limit: int) -> TimeTariffIntervalListResponse:
        """Fetches a page of TimeTariffInterval entities and returns them in a list response"""
        day = RateComponentManager.parse_rate_component_id(rate_component_id)

        rates = await select_tariff_rates_for_day(session, aggregator_id, tariff_id, site_id, day, start, after, limit)
        total_rates = await count_tariff_rates_for_day(session, aggregator_id, tariff_id, site_id, day, after)

        return TimeTariffIntervalMapper.map_to_list_response(rates, pricing_type, total_rates)

    @staticmethod
    async def fetch_time_tariff_interval(session: AsyncSession,
                                         aggregator_id: int,
                                         tariff_id: int,
                                         site_id: int,
                                         rate_component_id: str,
                                         time_tariff_interval: str,
                                         pricing_type: PricingReadingType) -> Optional[TimeTariffIntervalResponse]:
        """Fetches a single TimeTariffInterval entitiy matching the date/time. Time must be an exact
        match.

        Returns None if no rate exists for that interval/site

        rate_component_id and time_tariff_interval will be validated. raising InvalidMappingError if invalid"""

        day = RateComponentManager.parse_rate_component_id(rate_component_id)
        time_of_day = TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        generated_rate = await select_tariff_rate_for_day_time(session,
                                                               aggregator_id,
                                                               tariff_id,
                                                               site_id,
                                                               day,
                                                               time_of_day)
        if generated_rate is None:
            return None

        return TimeTariffIntervalMapper.map_to_response(generated_rate, pricing_type)


class ConsumptionTariffIntervalManager:
    @staticmethod
    def _generate_href(tariff_id: int, site_id: int, rate_component_id: str, time_tariff_interval: str, price: int):
        return f"/tp/{tariff_id}/{site_id}/rc/{quote(rate_component_id)}/tti/{quote(time_tariff_interval)}/cti/{price}/"

    @staticmethod
    async def fetch_consumption_tariff_interval_list(session: AsyncSession,
                                                     aggregator_id: int,
                                                     tariff_id: int,
                                                     site_id: int,
                                                     rate_component_id: str,
                                                     time_tariff_interval: str,
                                                     price: int) -> ConsumptionTariffIntervalListResponse:
        """This is a fully virtualised entity 'lookup' that only interacts with the DB to validate access.
        All the information required to build the response is passed in via params

        if site_id DNE is inaccessible to aggregator_id a NoResultFound will be raised

        rate_component_id and time_tariff_interval will be validated. raising InvalidMappingError if invalid"""

        # Validate ids
        RateComponentManager.parse_rate_component_id(rate_component_id)
        TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        # Validate access to site_id by aggregator_id
        if (await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)) is None:
            raise NoResultFound(f"site_id {site_id} is not accessible / does not exist")

        href = ConsumptionTariffIntervalManager._generate_href(
            tariff_id,
            site_id,
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
        """This is a fully virtualised entity 'lookup' that only interacts with the DB to validate access.
        All the information required to build the response is passed in via params

        if site_id DNE is inaccessible to aggregator_id a NoResultFound will be raised

        rate_component_id and time_tariff_interval will be validated. raising InvalidMappingError if invalid"""

        # Validate ids
        RateComponentManager.parse_rate_component_id(rate_component_id)
        TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        # Validate access to site_id by aggregator_id
        if (await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)) is None:
            raise NoResultFound(f"site_id {site_id} is not accessible / does not exist")

        href = ConsumptionTariffIntervalManager._generate_href(
            tariff_id,
            site_id,
            rate_component_id,
            time_tariff_interval,
            price)
        return ConsumptionTariffIntervalResponse.validate({
            "href": href,
            "consumptionBlock": ConsumptionBlockType.NOT_APPLICABLE,
            "price": price,
            "startValue": 0
        })
