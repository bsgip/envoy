from envoy_schema.admin.schema.aggregator import (
    AggregatorDomainPageResponse,
    AggregatorDomainRequest,
    AggregatorDomainResponse,
    AggregatorPageResponse,
    AggregatorRequest,
    AggregatorResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin import crud, mapper
from envoy.server import exception
from envoy.server.crud.aggregator import select_aggregator
from envoy.server.manager.time import utc_now


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
    async def fetch_single_aggregator(session: AsyncSession, aggregator_id: int) -> AggregatorResponse | None:
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


class AggregatorDomainManager:
    @staticmethod
    async def fetch_many_aggregator_domains(
        session: AsyncSession, aggregator_id: int, start: int, limit: int
    ) -> AggregatorDomainPageResponse | None:
        """Fetches a page of domains for the specified aggregator. Returns None if the aggregator does not exist"""
        if not await select_aggregator(session, aggregator_id):
            return None

        domains = await crud.aggregator.select_aggregator_domains(session, aggregator_id, start, limit)
        domain_count = await crud.aggregator.count_aggregator_domains(session, aggregator_id)
        return mapper.AggregatorDomainMapper.map_to_page_response(
            total_count=domain_count, start=start, limit=limit, aggregator_domains=domains
        )

    @staticmethod
    async def fetch_single_aggregator_domain(
        session: AsyncSession, aggregator_domain_id: int
    ) -> AggregatorDomainResponse | None:
        """Fetches a single aggregator domain by ID. Returns None if it does not exist"""
        domain = await crud.aggregator.select_aggregator_domain(session, aggregator_domain_id)
        if domain is None:
            return None
        return mapper.AggregatorDomainMapper.map_to_response(domain)

    @staticmethod
    async def add_new_aggregator_domain(
        session: AsyncSession, aggregator_id: int, request: AggregatorDomainRequest
    ) -> int:
        """Adds a new domain to the specified aggregator. Returns the new aggregator_domain_id.

        Raises NotFoundError if the aggregator does not exist"""
        if not await select_aggregator(session, aggregator_id):
            raise exception.NotFoundError(f"Aggregator with id {aggregator_id} not found")

        domain = mapper.AggregatorDomainMapper.map_from_request(aggregator_id, utc_now(), request)
        await crud.aggregator.insert_single_aggregator_domain(session, domain)
        aggregator_domain_id = domain.aggregator_domain_id
        await session.commit()
        return aggregator_domain_id

    @staticmethod
    async def update_existing_aggregator_domain(
        session: AsyncSession, aggregator_domain_id: int, request: AggregatorDomainRequest
    ) -> None:
        """Updates the domain value of an existing aggregator domain.

        Raises NotFoundError if the aggregator domain does not exist"""
        domain = await crud.aggregator.select_aggregator_domain(session, aggregator_domain_id)
        if domain is None:
            raise exception.NotFoundError(f"AggregatorDomain with id {aggregator_domain_id} not found")

        domain.domain = request.domain
        domain.changed_time = utc_now()
        await session.commit()

    @staticmethod
    async def delete_aggregator_domain(session: AsyncSession, aggregator_domain_id: int) -> None:
        """Permanently deletes an existing aggregator domain.

        Raises NotFoundError if the aggregator domain does not exist"""
        if not await crud.aggregator.delete_single_aggregator_domain(session, aggregator_domain_id):
            raise exception.NotFoundError(f"AggregatorDomain with id {aggregator_domain_id} not found")
        await session.commit()
