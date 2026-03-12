from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.pricing import (
    count_active_rates_include_deleted,
    count_tariff_components_by_tariff,
    select_active_rates_include_deleted,
    select_all_tariffs,
    select_single_tariff,
    select_tariff_component_by_id,
    select_tariff_components_by_tariff,
    select_tariff_count,
    select_tariff_generated_rate_include_deleted,
)
from envoy.server.crud.site import select_single_site_with_site_id
from envoy.server.exception import NotFoundError
from envoy.server.manager.time import utc_now
from envoy.server.mapper.sep2.pricing import (
    CONSUMPTION_TARIFF_INTERVAL_ID,
    ConsumptionTariffIntervalMapper,
    RateComponentMapper,
    TariffProfileMapper,
    TimeTariffIntervalMapper,
)
from envoy.server.request_scope import SiteRequestScope


class TariffProfileManager:
    @staticmethod
    async def fetch_tariff_profile(
        session: AsyncSession, scope: SiteRequestScope, tariff_id: int
    ) -> Optional[TariffProfileResponse]:
        """Fetches a single tariff in the form of a sep2 TariffProfile thats specific to a single site."""

        tariff = await select_single_tariff(session, tariff_id)
        if tariff is None:
            return None

        now = utc_now()
        total_components = await count_tariff_components_by_tariff(session, tariff_id, None)
        total_rates = await count_active_rates_include_deleted(
            session, tariff_id, None, scope.site_id, now, datetime.min
        )
        return TariffProfileMapper.map_to_response(scope, tariff, total_components, total_rates)

    @staticmethod
    async def fetch_tariff_profile_list(
        session: AsyncSession,
        scope: SiteRequestScope,
        start: int,
        changed_after: datetime,
        limit: int,
        fsa_id: Optional[int],
    ) -> Optional[TariffProfileListResponse]:
        """Fetches all tariffs accessible to a specific site (and optionally scoped to a specific function set
        assignment id)."""

        tariffs = await select_all_tariffs(session, start, changed_after, limit, fsa_id)
        tariff_count = await select_tariff_count(session, changed_after, fsa_id)

        # we need the component/rate counts associated with each Tariff+Site.
        now = utc_now()
        tariff_rate_counts: list[int] = []
        tariff_component_counts: list[int] = []
        for tariff in tariffs:
            total_components = await count_tariff_components_by_tariff(session, tariff.tariff_id, None)
            tariff_component_counts.append(total_components)

            total_rates = await count_active_rates_include_deleted(
                session, tariff.tariff_id, None, scope.site_id, now, datetime.min
            )
            tariff_rate_counts.append(total_rates)

        return TariffProfileMapper.map_to_list_response(
            scope, zip(tariffs, tariff_component_counts, tariff_rate_counts), tariff_count, fsa_id
        )


class RateComponentManager:

    @staticmethod
    async def fetch_rate_component(
        session: AsyncSession,
        scope: SiteRequestScope,
        tariff_id: int,
        rate_component_id: int,
    ) -> Optional[RateComponentResponse]:
        """Fetches a RateComponent underneath a specific tariff_id - returns None if it DNE"""

        tc = await select_tariff_component_by_id(session, rate_component_id)
        if tc is None or tc.tariff_id != tariff_id:
            return None

        now = utc_now()
        total_rates = await count_active_rates_include_deleted(
            session, tariff_id, rate_component_id, scope.site_id, now, changed_after=datetime.min
        )
        return RateComponentMapper.map_to_response(scope, tc, total_rates)

    @staticmethod
    async def fetch_rate_component_list(
        session: AsyncSession,
        scope: SiteRequestScope,
        tariff_id: int,
        start: int,
        changed_after: Optional[datetime],
        limit: int,
    ) -> RateComponentListResponse:
        """Fetches all RateComponent's underneath a specific Tariff via a list endpoint"""

        now = utc_now()

        tcs = await select_tariff_components_by_tariff(session, tariff_id, start, changed_after, limit)
        tc_count = await count_tariff_components_by_tariff(session, tariff_id, changed_after)

        tcs_rate_counts: list[int] = []
        for tc in tcs:
            tcs_rate_counts.append(
                await count_active_rates_include_deleted(
                    session, tariff_id, tc.tariff_component_id, scope.site_id, now, changed_after
                )
            )

        return RateComponentMapper.map_to_list_response(scope, tariff_id, list(zip(tcs, tcs_rate_counts)), tc_count)


class TimeTariffIntervalManager:

    @staticmethod
    async def fetch_time_tariff_interval_list(
        session: AsyncSession,
        scope: SiteRequestScope,
        tariff_id: int,
        rate_component_id: int,
        start: int,
        after: datetime,
        limit: int,
    ) -> TimeTariffIntervalListResponse:
        """Fetches a page of TimeTariffInterval entities and returns them in a list response. Raises NotFoundError
        if the specified site scope DNE"""

        existing_site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        if existing_site is None:
            raise NotFoundError(f"/edev/{scope.site_id} does not exist / is inaccessible.")

        now = utc_now()
        rates = await select_active_rates_include_deleted(
            session, tariff_id, rate_component_id, existing_site, now, start, after, limit
        )
        total_rates = await count_active_rates_include_deleted(
            session, tariff_id, rate_component_id, existing_site.site_id, now, after
        )

        return TimeTariffIntervalMapper.map_to_list_response(
            scope, tariff_id, rate_component_id, now, rates, total_rates
        )

    @staticmethod
    async def fetch_combined_time_tariff_interval_list(
        session: AsyncSession,
        scope: SiteRequestScope,
        tariff_id: int,
        start: int,
        after: datetime,
        limit: int,
    ) -> TimeTariffIntervalListResponse:
        """Fetches a page of TimeTariffInterval entities (across every RateComponent) for the specified site and returns
        them in a list response. Raises NotFoundError if the specified site scope DNE"""

        existing_site = await select_single_site_with_site_id(session, scope.site_id, scope.aggregator_id)
        if existing_site is None:
            raise NotFoundError(f"/edev/{scope.site_id} does not exist / is inaccessible.")

        now = utc_now()
        rates = await select_active_rates_include_deleted(
            session, tariff_id, None, existing_site, now, start, after, limit
        )
        total_rates = await count_active_rates_include_deleted(
            session, tariff_id, None, existing_site.site_id, now, after
        )

        return TimeTariffIntervalMapper.map_to_list_response(scope, tariff_id, None, now, rates, total_rates)

    @staticmethod
    async def fetch_time_tariff_interval(
        session: AsyncSession,
        scope: SiteRequestScope,
        tariff_id: int,
        rate_component_id: int,
        time_tariff_interval_id: int,
    ) -> Optional[TimeTariffIntervalResponse]:
        """Fetches a single TimeTariffInterval entity for the specified id

        Returns None if no rate exists for that id/site"""

        rate = await select_tariff_generated_rate_include_deleted(
            session, scope.aggregator_id, scope.site_id, time_tariff_interval_id
        )
        if rate is None or rate.tariff_id != tariff_id or rate.tariff_component_id != rate_component_id:
            return None

        now = utc_now()
        return TimeTariffIntervalMapper.map_to_response(scope, now, rate)


class ConsumptionTariffIntervalManager:
    @staticmethod
    async def fetch_consumption_tariff_interval_list(
        session: AsyncSession,
        scope: SiteRequestScope,
        tariff_id: int,
        rate_component_id: int,
        time_tariff_interval_id: int,
    ) -> ConsumptionTariffIntervalListResponse:
        """This list is semi-virtual. It's backed by a DB record but there can only ever be a single entry"""

        rate = await select_tariff_generated_rate_include_deleted(
            session, scope.aggregator_id, scope.site_id, time_tariff_interval_id
        )
        if rate is None or rate.tariff_id != tariff_id or rate.tariff_component_id != rate_component_id:
            raise NotFoundError(f"No price record for /edev/{scope.site_id} under {tariff_id=} {rate_component_id=}")

        return ConsumptionTariffIntervalMapper.map_to_list_response(scope, rate)

    @staticmethod
    async def fetch_consumption_tariff_interval(
        session: AsyncSession,
        scope: SiteRequestScope,
        tariff_id: int,
        rate_component_id: int,
        time_tariff_interval_id: int,
        consumption_tariff_interval_id: int,
    ) -> ConsumptionTariffIntervalResponse:
        """ """

        if consumption_tariff_interval_id != CONSUMPTION_TARIFF_INTERVAL_ID:
            raise NotFoundError(f"No ConsumptionTariffInterval with that href.")

        rate = await select_tariff_generated_rate_include_deleted(
            session, scope.aggregator_id, scope.site_id, time_tariff_interval_id
        )
        if rate is None or rate.tariff_id != tariff_id or rate.tariff_component_id != rate_component_id:
            raise NotFoundError(f"No price record for /edev/{scope.site_id} under {tariff_id=} {rate_component_id=}")

        return ConsumptionTariffIntervalMapper.map_to_response(scope, rate, consumption_tariff_interval_id)
