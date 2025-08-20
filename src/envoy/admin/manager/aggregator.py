from typing import Optional

from envoy_schema.admin.schema.aggregator import AggregatorPageResponse, AggregatorResponse, AggregatorRequest
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin import crud
from envoy.admin import mapper
from envoy.server.crud.aggregator import select_aggregator
from envoy.server.manager.time import utc_now
from envoy.server import exception


class AggregatorManager:
    @staticmethod
    async def fetch_many_aggregators(session: AsyncSession, start: int, limit: int) -> AggregatorPageResponse:
        """Select many aggregators from the DB and map to a list of AggregatorResponse objects"""
        agg_list = await crud.aggregator.select_all_aggregators(session, start, limit)
        agg_count = await crud.aggregator.count_all_aggregators(session)
        return mapper.AggregatorMapper.map_to_page_response(
            total_count=agg_count, start=start, limit=limit, aggregators=agg_list
        )

    @staticmethod
    async def fetch_single_aggregator(session: AsyncSession, aggregator_id: int) -> Optional[AggregatorResponse]:
        """Select a single aggregator and return the mapped AggregatorResponse object. Returns None if the
        aggregator ID does not exist"""
        aggregator = await select_aggregator(session, aggregator_id)
        if aggregator is None:
            return None
        return mapper.AggregatorMapper.map_to_response(aggregator)

    @staticmethod
    async def add_new_aggregator(session: AsyncSession, aggregator: AggregatorRequest) -> int:
        """Map an AggregatorRequest object to an Aggregator model and insert into DB. Return the aggregator_id only."""

        changed_time = utc_now()
        agg_model = mapper.AggregatorMapper.map_from_request(changed_time, aggregator)
        await crud.aggregator.insert_single_aggregator(session, agg_model)
        await session.commit()
        return agg_model.aggregator_id

    @staticmethod
    async def update_existing_aggregator(
        session: AsyncSession,
        aggregator_id: int,
        aggregator: AggregatorRequest,
    ) -> None:
        """Map a AggregatorRequest object to a Aggregator model and update DB entry."""

        if not await select_aggregator(session, aggregator_id):
            raise exception.NotFoundError(f"Aggregator with id {aggregator_id} not found")
        changed_time = utc_now()
        agg_model = mapper.AggregatorMapper.map_from_request(changed_time, aggregator)
        agg_model.aggregator_id = aggregator_id
        await crud.aggregator.update_single_aggregator(session, agg_model)
        await session.commit()
