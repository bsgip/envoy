from itertools import product
import datetime as dt

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.aggregator import AggregatorDomain as AggregatorDomainResponse
from envoy_schema.admin.schema.aggregator import AggregatorPageResponse, AggregatorResponse, AggregatorRequest

from envoy.admin.mapper.aggregator import AggregatorMapper
from envoy.server.model.aggregator import Aggregator


@pytest.mark.parametrize("optional_is_none, has_domains", product([True, False], [True, False]))
def test_aggregator_to_response(optional_is_none: bool, has_domains: bool):
    """Asserts that the type mapping is a straight passthrough of properties"""
    agg: Aggregator = generate_class_instance(
        Aggregator, optional_is_none=optional_is_none, generate_relationships=has_domains
    )
    mdl = AggregatorMapper.map_to_response(agg)

    assert isinstance(mdl, AggregatorResponse)

    assert_class_instance_equality(AggregatorResponse, agg, mdl)

    if has_domains:
        assert len(agg.domains) > 0
        assert len(mdl.domains) == len(agg.domains)
        assert_list_type(AggregatorDomainResponse, mdl.domains)
        for e, a in zip(agg.domains, mdl.domains):
            assert_class_instance_equality(AggregatorDomainResponse, e, a)
    else:
        assert len(mdl.domains) == 0


def test_aggregator_to_page_response():
    agg1: Aggregator = generate_class_instance(Aggregator, seed=101, optional_is_none=True, generate_relationships=True)
    agg2: Aggregator = generate_class_instance(
        Aggregator, seed=202, optional_is_none=False, generate_relationships=False
    )
    total_count = 11
    start = 22
    limit = 33
    mdl = AggregatorMapper.map_to_page_response(total_count, start, limit, [agg1, agg2])

    assert isinstance(mdl, AggregatorPageResponse)
    assert len(mdl.aggregators) == 2
    assert all([isinstance(a, AggregatorResponse) for a in mdl.aggregators])
    assert mdl.limit == limit
    assert mdl.start == start
    assert mdl.total_count == total_count


def test_aggregator_from_request() -> None:
    """Tests mapping from a request"""
    req = AggregatorRequest(name="Some new aggregator")

    change_time = dt.datetime(1234, 5, 6, 7, 8, 9, tzinfo=dt.timezone.utc)
    agg = AggregatorMapper.map_from_request(change_time, req)

    assert isinstance(agg, Aggregator)
    assert agg.name == "Some new aggregator"
    assert agg.changed_time == change_time
