from typing import Iterable

import envoy_schema.admin.schema.aggregator as schema_agg
import envoy.server.model.aggregator as model_agg


class AggregatorMapper:
    @staticmethod
    def map_to_response(aggregator: model_agg.Aggregator) -> schema_agg.AggregatorResponse:
        """Converts an internal Aggregator model to the schema AggregatorResponse"""

        domains = aggregator.domains
        if domains is None:
            domains = []

        return schema_agg.AggregatorResponse(
            aggregator_id=aggregator.aggregator_id,
            name=aggregator.name,
            domains=[
                schema_agg.AggregatorDomain(domain=d.domain, changed_time=d.changed_time, created_time=d.created_time)
                for d in domains
            ],
        )


    @staticmethod
    def map_from_request(aggregator: schema_agg.AggregatorRequest) -> model_agg.Aggregator:
        """Converts an AggregatorResponse to an Aggregator""" 

        return model_agg.Aggregator(
            name=aggregator.name,
            created_time=aggregator.created_time,
            changed_time=aggregator.changed_time,
            domains=[
                model_agg.AggregatorDomain(domain=d.domain, changed_time=d.changed_time, created_time=d.created_time)
                for d in aggregator.domains
            ]
        )


    @staticmethod
    def map_to_page_response(
        total_count: int, start: int, limit: int, aggregators: Iterable[model_agg.Aggregator]
    ) -> schema_agg.AggregatorPageResponse:
        """Converts a page of Aggregator models to the schema AggregatorPageResponse"""
        return schema_agg.AggregatorPageResponse(
            total_count=total_count,
            start=start,
            limit=limit,
            aggregators=[AggregatorMapper.map_to_response(a) for a in aggregators],
        )
