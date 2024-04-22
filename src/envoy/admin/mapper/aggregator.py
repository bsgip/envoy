from typing import Iterable

from envoy_schema.admin.schema.aggregator import AggregatorDomain, AggregatorPageResponse, AggregatorResponse

from envoy.server.model.aggregator import Aggregator


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
            domains=[AggregatorDomain(domain=d.domain, changed_time=d.changed_time) for d in domains],
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
