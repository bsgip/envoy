import datetime as dt
from collections.abc import Iterable

from envoy_schema.admin.schema.aggregator import (
    AggregatorDomain,
    AggregatorDomainPageResponse,
    AggregatorDomainRequest,
    AggregatorDomainResponse,
    AggregatorPageResponse,
    AggregatorRequest,
    AggregatorResponse,
)

from envoy.server.model.aggregator import Aggregator
from envoy.server.model.aggregator import AggregatorDomain as AggregatorDomainModel


class AggregatorMapper:
    @staticmethod
    def map_to_response(aggregator: Aggregator) -> AggregatorResponse:
        """Converts an internal Aggregator model to the schema AggregatorResponse"""

        domains = aggregator.domains
        if domains is None:
            domains = []

        return AggregatorResponse(
            aggregator_id=aggregator.aggregator_id,
            name=aggregator.name,
            domains=[
                AggregatorDomain(domain=d.domain, changed_time=d.changed_time, created_time=d.created_time)
                for d in domains
            ],
        )

    @staticmethod
    def map_to_page_response(
        total_count: int, start: int, limit: int, aggregators: Iterable[Aggregator]
    ) -> AggregatorPageResponse:
        """Converts a page of Aggregator models to the schema AggregatorPageResponse"""
        return AggregatorPageResponse(
            total_count=total_count,
            start=start,
            limit=limit,
            aggregators=[AggregatorMapper.map_to_response(a) for a in aggregators],
        )

    @staticmethod
    def map_from_request(changed_time: dt.datetime, aggregator: AggregatorRequest) -> Aggregator:
        return Aggregator(
            name=aggregator.name,
            changed_time=changed_time,
        )


class AggregatorDomainMapper:
    @staticmethod
    def map_to_response(aggregator_domain: AggregatorDomainModel) -> AggregatorDomainResponse:
        """Converts an internal AggregatorDomain model to the schema AggregatorDomainResponse"""
        return AggregatorDomainResponse(
            aggregator_domain_id=aggregator_domain.aggregator_domain_id,
            aggregator_id=aggregator_domain.aggregator_id,
            created_time=aggregator_domain.created_time,
            changed_time=aggregator_domain.changed_time,
            domain=aggregator_domain.domain,
        )

    @staticmethod
    def map_to_page_response(
        total_count: int, start: int, limit: int, aggregator_domains: Iterable[AggregatorDomainModel]
    ) -> AggregatorDomainPageResponse:
        """Converts a page of AggregatorDomain models to the schema AggregatorDomainPageResponse"""
        return AggregatorDomainPageResponse(
            total_count=total_count,
            start=start,
            limit=limit,
            aggregator_domains=[AggregatorDomainMapper.map_to_response(d) for d in aggregator_domains],
        )

    @staticmethod
    def map_from_request(
        aggregator_id: int, changed_time: dt.datetime, request: AggregatorDomainRequest
    ) -> AggregatorDomainModel:
        """Converts an AggregatorDomainRequest into a (new) AggregatorDomain model for aggregator_id"""
        return AggregatorDomainModel(
            aggregator_id=aggregator_id,
            changed_time=changed_time,
            domain=request.domain,
        )
