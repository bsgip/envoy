from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.billing import fetch_aggregator, fetch_billing_data
from envoy.admin.mapper.billing import BillingMapper
from envoy.admin.schema.billing import BillingResponse
from envoy.server.exception import NotFoundError


class BillingManager:
    @staticmethod
    async def generate_billing_report(
        session: AsyncSession, aggregator_id: int, tariff_id: int, period_start: datetime, period_end: datetime
    ) -> BillingResponse:
        """Generates billing report data for a specific time period/aggregator. Raises NotFoundError if aggregator_id
        isn't registered in the system"""
        aggregator = await fetch_aggregator(session, aggregator_id=aggregator_id)
        if aggregator is None:
            raise NotFoundError(f"Aggregator ID {aggregator_id} couldn't be found")

        billing_data = await fetch_billing_data(
            session, aggregator_id=aggregator_id, tariff_id=tariff_id, period_start=period_start, period_end=period_end
        )

        return BillingMapper.map_to_response(aggregator, tariff_id, period_start, period_end, billing_data)
