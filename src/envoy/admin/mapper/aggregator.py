from typing import Iterable

import datetime as dt

from envoy_schema.admin.schema.aggregator import (
    AggregatorDomain,
    AggregatorPageResponse,
    AggregatorResponse,
    AggregatorRequest,
)

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
