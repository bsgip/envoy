from datetime import datetime

from envoy_schema.admin.schema.billing import (
    AggregatorBillingResponse,
    CalculationLogBillingResponse,
    SiteBillingRequest,
    SiteBillingResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.billing import (
    fetch_aggregator,
    fetch_aggregator_billing_data,
    fetch_calculation_log_billing_data,
    fetch_sites_billing_data,
)
from envoy.admin.crud.log import select_calculation_log_by_id
from envoy.admin.mapper.billing import BillingMapper
from envoy.server.exception import NotFoundError


class BillingManager:
    @staticmethod
    async def generate_aggregator_billing_report(
        session: AsyncSession, aggregator_id: int, tariff_id: int, period_start: datetime, period_end: datetime
    ) -> AggregatorBillingResponse:
        """Generates billing report data for a specific time period/aggregator. Raises NotFoundError if aggregator_id
        isn't registered in the system"""
        aggregator = await fetch_aggregator(session, aggregator_id=aggregator_id)
        if aggregator is None:
            raise NotFoundError(f"Aggregator ID {aggregator_id} couldn't be found")

        billing_data = await fetch_aggregator_billing_data(
            session, aggregator_id=aggregator_id, tariff_id=tariff_id, period_start=period_start, period_end=period_end
        )

        return BillingMapper.map_to_aggregator_response(aggregator, tariff_id, period_start, period_end, billing_data)

    @staticmethod
    async def generate_sites_billing_report(session: AsyncSession, request: SiteBillingRequest) -> SiteBillingResponse:
        """Generates billing report data for a specific time period/set of sites."""
        billing_data = await fetch_sites_billing_data(
            session,
            site_ids=request.site_ids,
            tariff_id=request.tariff_id,
            period_start=request.period_start,
            period_end=request.period_end,
        )

        return BillingMapper.map_to_sites_response(
            request.site_ids, request.tariff_id, request.period_start, request.period_end, billing_data
        )

    @staticmethod
    async def generate_calculation_log_billing_report(
        session: AsyncSession, calculation_log_id: int, tariff_id: int
    ) -> CalculationLogBillingResponse:
        """Generates billing report data for a specific calculation log. Raises NotFoundError if calculation log
        isn't registered in the system"""

        calculation_log = await select_calculation_log_by_id(session, calculation_log_id, False, False)
        if calculation_log is None:
            raise NotFoundError(f"CalculationLog ID {calculation_log_id} couldn't be found")

        billing_data = await fetch_calculation_log_billing_data(
            session, calculation_log=calculation_log, tariff_id=tariff_id
        )

        return BillingMapper.map_to_calculation_log_response(calculation_log, tariff_id, billing_data)
