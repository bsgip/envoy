from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.api.request import extract_date_from_iso_string
from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.crud.pricing import (
    TariffGeneratedRateDailyStats,
    count_tariff_rates_for_day,
    count_unique_rate_days,
    select_all_tariffs,
    select_rate_daily_stats,
    select_single_tariff,
    select_tariff_count,
    select_tariff_rate_for_day_time,
    select_tariff_rates_for_day,
)
from envoy.server.exception import InvalidIdError, NotFoundError
from envoy.server.mapper.sep2.pricing import (
    TOTAL_PRICING_READING_TYPES,
    ConsumptionTariffIntervalMapper,
    PricingReadingType,
    RateComponentMapper,
    TariffProfileMapper,
    TimeTariffIntervalMapper,
)
from envoy.server.model.tariff import PRICE_DECIMAL_POWER
from envoy.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)


class TariffProfileManager:
    @staticmethod
    async def fetch_tariff_profile(
        session: AsyncSession, aggregator_id: int, tariff_id: int, site_id: int
    ) -> Optional[TariffProfileResponse]:
        """Fetches a single tariff in the form of a sep2 TariffProfile thats specific to a single site."""

        tariff = await select_single_tariff(session, tariff_id)
        if tariff is None:
            return None

        unique_rate_days = await count_unique_rate_days(session, aggregator_id, tariff_id, site_id, datetime.min)
        return TariffProfileMapper.map_to_response(tariff, site_id, unique_rate_days * TOTAL_PRICING_READING_TYPES)

    @staticmethod
    async def fetch_tariff_profile_list(
        session: AsyncSession, aggregator_id: int, site_id: int, start: int, changed_after: datetime, limit: int
    ) -> Optional[TariffProfileListResponse]:
        """Fetches all tariffs accessible to a specific site."""

        tariffs = await select_all_tariffs(session, start, changed_after, limit)
        tariff_count = await select_tariff_count(session, changed_after)

        # we need the rate counts associated with each Tariff+Site. Those are derived from dates with a Rate
        tariff_rate_counts: list[int] = []
        for tariff in tariffs:
            rate_days = await count_unique_rate_days(session, aggregator_id, tariff.tariff_id, site_id, changed_after)
            tariff_rate_counts.append(rate_days * TOTAL_PRICING_READING_TYPES)

        return TariffProfileMapper.map_to_list_response(zip(tariffs, tariff_rate_counts), tariff_count, site_id)

    @staticmethod
    async def fetch_tariff_profile_no_site(session: AsyncSession, tariff_id: int) -> Optional[TariffProfileResponse]:
        """Fetches a single tariff in the form of a sep2 TariffProfile. This tariff will NOT contain
        any useful RateComponent links due to a lack of a site ID scope

        Its expected that function set assignments will assign appropriate tariff links"""
        tariff = await select_single_tariff(session, tariff_id)
        if tariff is None:
            return None

        return TariffProfileMapper.map_to_nosite_response(tariff)

    @staticmethod
    async def fetch_tariff_profile_list_no_site(
        session: AsyncSession, start: int, changed_after: datetime, limit: int
    ) -> Optional[TariffProfileListResponse]:
        """Fetches a tariff list in the form of a sep2 TariffProfileList. These tariffs will NOT contain
        any useful RateComponent links due to a lack of a site ID scope.

        Its expected that function set assignments will assign appropriate tariff links"""
        tariffs = await select_all_tariffs(session, start, changed_after, limit)
        tariff_count = await select_tariff_count(session, changed_after)

        return TariffProfileMapper.map_to_list_nosite_response(tariffs, tariff_count)


class RateComponentManager:
    @staticmethod
    def parse_rate_component_id(id: str) -> date:
        """Validates that id looks like YYYY-MM-DD. Returns parsed date object if it does
        otherwise raises InvalidIdError"""
        date = extract_date_from_iso_string(id)
        if date is None:
            raise InvalidIdError(f"Expected YYYY-MM-DD for rate_component_id but got {id}")

        return date

    @staticmethod
    async def fetch_rate_component(
        session: AsyncSession,
        aggregator_id: int,
        tariff_id: int,
        site_id: int,
        rate_component_id: str,
        pricing_type: PricingReadingType,
    ) -> RateComponentResponse:
        """RateComponent is a fully virtual entity - it has no corresponding model in our DB - it's essentially
        just a placeholder for date + price type filtering

        This function will construct the RateComponent directly"""

        day = RateComponentManager.parse_rate_component_id(rate_component_id)
        count = await count_tariff_rates_for_day(session, aggregator_id, tariff_id, site_id, day, datetime.min)
        return RateComponentMapper.map_to_response(count, tariff_id, site_id, pricing_type, day)

    @staticmethod
    async def fetch_rate_component_list(
        session: AsyncSession,
        aggregator_id: int,
        tariff_id: int,
        site_id: int,
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> RateComponentListResponse:
        """RateComponent is a fully virtual entity - it has no corresponding model in our DB - it's essentially
        just a placeholder for date + price type filtering.

        This function will emulate pagination by taking the dates with rates and then virtually expanding the page
        to account for iterating the various pricing readings"""

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
        rate_stats: TariffGeneratedRateDailyStats = await select_rate_daily_stats(
            session, aggregator_id, tariff_id, site_id, db_adjusted_start, changed_after, db_adjusted_limit
        )

        # If we are starting from a value that doesn't align with a multiple of TOTAL_PRICING_READING_TYPES we will
        # need to cull those entries that exist before our real start value
        leading_items_to_remove = db_adjusted_start_remainder

        # if the client limit could actually "bite" we need to consider culling items off the end of the list
        # to respect it
        trailing_items_to_remove = 0
        if (limit + leading_items_to_remove) < (len(rate_stats.single_date_counts) * TOTAL_PRICING_READING_TYPES):
            trailing_items_to_remove = (
                TOTAL_PRICING_READING_TYPES - db_adjusted_limit_remainder
            ) % TOTAL_PRICING_READING_TYPES  # noqa e501

        return RateComponentMapper.map_to_list_response(
            rate_stats, leading_items_to_remove, trailing_items_to_remove, tariff_id, site_id
        )


class TimeTariffIntervalManager:
    @staticmethod
    def parse_time_tariff_interval_id(id: str) -> time:
        """Validates that id looks like HH:MM. Returns parsed time object if it does
        otherwise raises InvalidIdError"""
        # certain python versions allow all sorts of funny things through so we layer some additional
        # checks over the top of the isoformat
        if len(id) != 5 or id[2] != ":":
            raise InvalidIdError(f"Expected HH:MM for time_tariff_interval_id but got {id}")

        try:
            return time.fromisoformat(id)
        except ValueError:
            raise InvalidIdError(f"Expected HH:MM for time_tariff_interval_id but got {id}")

    @staticmethod
    async def fetch_time_tariff_interval_list(
        session: AsyncSession,
        aggregator_id: int,
        tariff_id: int,
        site_id: int,
        rate_component_id: str,
        pricing_type: PricingReadingType,
        start: int,
        after: datetime,
        limit: int,
    ) -> TimeTariffIntervalListResponse:
        """Fetches a page of TimeTariffInterval entities and returns them in a list response"""
        day = RateComponentManager.parse_rate_component_id(rate_component_id)

        rates = await select_tariff_rates_for_day(session, aggregator_id, tariff_id, site_id, day, start, after, limit)
        total_rates = await count_tariff_rates_for_day(session, aggregator_id, tariff_id, site_id, day, after)

        return TimeTariffIntervalMapper.map_to_list_response(rates, pricing_type, total_rates)

    @staticmethod
    async def fetch_time_tariff_interval(
        session: AsyncSession,
        aggregator_id: int,
        tariff_id: int,
        site_id: int,
        rate_component_id: str,
        time_tariff_interval: str,
        pricing_type: PricingReadingType,
    ) -> Optional[TimeTariffIntervalResponse]:
        """Fetches a single TimeTariffInterval entity matching the date/time. Time must be an exact
        match.

        Returns None if no rate exists for that interval/site

        rate_component_id and time_tariff_interval will be validated. raising InvalidIdError if invalid"""

        day = RateComponentManager.parse_rate_component_id(rate_component_id)
        time_of_day = TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        generated_rate = await select_tariff_rate_for_day_time(
            session, aggregator_id, tariff_id, site_id, day, time_of_day
        )
        if generated_rate is None:
            return None

        return TimeTariffIntervalMapper.map_to_response(generated_rate, pricing_type)


class ConsumptionTariffIntervalManager:
    @staticmethod
    async def fetch_consumption_tariff_interval_list(
        session: AsyncSession,
        aggregator_id: int,
        tariff_id: int,
        site_id: int,
        rate_component_id: str,
        pricing_type: PricingReadingType,
        time_tariff_interval: str,
        sep2_price: int,
    ) -> ConsumptionTariffIntervalListResponse:
        """This is a fully virtualised entity 'lookup' that only interacts with the DB to validate access.
        All the information required to build the response is passed in via params

        sep2_price should be an integer price that a sep2 client will communicate

        if site_id does not exist or is inaccessible to aggregator_id a NotFoundError will be raised

        rate_component_id and time_tariff_interval will be validated. raising InvalidIdError if invalid"""

        # Validate ids
        day = RateComponentManager.parse_rate_component_id(rate_component_id)
        time_of_day = TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        # Validate access to site_id by aggregator_id
        if (await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)) is None:
            raise NotFoundError(f"site_id {site_id} is not accessible / does not exist")

        price = Decimal(sep2_price) / Decimal(PRICE_DECIMAL_POWER)
        return ConsumptionTariffIntervalMapper.map_to_list_response(
            tariff_id, site_id, pricing_type, day, time_of_day, price
        )

    @staticmethod
    async def fetch_consumption_tariff_interval(
        session: AsyncSession,
        aggregator_id: int,
        tariff_id: int,
        site_id: int,
        rate_component_id: str,
        pricing_type: PricingReadingType,
        time_tariff_interval: str,
        sep2_price: int,
    ) -> ConsumptionTariffIntervalResponse:
        """This is a fully virtualised entity 'lookup' that only interacts with the DB to validate access.
        All the information required to build the response is passed in via params

        sep2_price should be an integer price that a sep2 client will communicate

        if site_id does not exist or is inaccessible to aggregator_id a NotFoundError will be raised

        rate_component_id and time_tariff_interval will be validated. raising InvalidIdError if invalid"""

        # Validate ids
        day = RateComponentManager.parse_rate_component_id(rate_component_id)
        time_of_day = TimeTariffIntervalManager.parse_time_tariff_interval_id(time_tariff_interval)

        # Validate access to site_id by aggregator_id
        if (await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=aggregator_id)) is None:
            raise NotFoundError(f"site_id {site_id} is not accessible / does not exist")

        price = Decimal(sep2_price) / Decimal(PRICE_DECIMAL_POWER)
        return ConsumptionTariffIntervalMapper.map_to_response(
            tariff_id, site_id, pricing_type, day, time_of_day, price
        )
