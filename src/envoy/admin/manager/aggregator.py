from typing import Optional

from envoy_schema.admin.schema.aggregator import AggregatorPageResponse, AggregatorResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.aggregator import count_all_aggregators, select_all_aggregators
from envoy.admin.mapper.aggregator import AggregatorMapper
from envoy.server.crud.aggregator import select_aggregator


class AggregatorManager:
    @staticmethod
    async def fetch_many_aggregators(session: AsyncSession, start: int, limit: int) -> AggregatorPageResponse:
        """Select many aggregators from the DB and map to a list of AggregatorResponse objects"""
        agg_list = await select_all_aggregators(session, start, limit)
        agg_count = await count_all_aggregators(session)
        return AggregatorMapper.map_to_page_response(
            total_count=agg_count, start=start, limit=limit, aggregators=agg_list
        )

    @staticmethod
    async def fetch_single_aggregator(session: AsyncSession, aggregator_id: int) -> Optional[AggregatorResponse]:
        """Select a single aggregator and return the mapped AggregatorResponse object. Returns None if the
        aggregator ID does not exist"""
        aggregator = await select_aggregator(session, aggregator_id)
        if aggregator is None:
            return None
        return AggregatorMapper.map_to_response(aggregator)
