import unittest.mock as mock
from datetime import date, datetime, timezone

import pytest
from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier

from envoy.notification.crud.batch import (
    AggregatorBatchedEntities,
    TResourceModel,
    get_batch_key,
    get_site_id,
    get_subscription_filter_id,
    select_subscriptions_for_resource,
)
from envoy.notification.exception import NotificationError
from envoy.server.crud.end_device import Site
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance
from tests.postgres_testing import generate_async_session


@pytest.mark.parametrize("resource", [(r) for r in SubscriptionResource])
def test_AggregatorBatchedEntities_empty(resource: SubscriptionResource):
    """Simple sanity check that empty lists dont crash out"""
    ts = datetime(2024, 1, 2, 3, 4, 5)
    b = AggregatorBatchedEntities(ts, resource, [])

    assert b.timestamp == ts
    assert len(b.models_by_batch_key) == 0


@mock.patch("envoy.notification.crud.batch.get_batch_key")
@pytest.mark.parametrize("resource", [(r) for r in SubscriptionResource])
def test_AggregatorBatchedEntities_single_batch(mock_get_batch_key: mock.MagicMock, resource: SubscriptionResource):
    """This completely isolates the batching algorithm from the use of get_batch_key / the underlying models"""

    # Everything in this test will be a single batch
    fake_entity_1 = {"batch_key": (1, 2)}
    fake_entity_2 = {"batch_key": (1, 2)}
    fake_entity_3 = {"batch_key": (1, 2)}
    fake_entity_4 = {"batch_key": (1, 2)}

    mock_get_batch_key.side_effect = lambda r, m: m["batch_key"]

    ts = datetime(2024, 1, 2, 3, 4, 6)
    b = AggregatorBatchedEntities(ts, resource, [fake_entity_1, fake_entity_2, fake_entity_3, fake_entity_4])

    assert b.timestamp == ts
    assert len(b.models_by_batch_key) == 1, "Expecting a single unique key"
    assert b.models_by_batch_key[(1, 2)] == [fake_entity_1, fake_entity_2, fake_entity_3, fake_entity_4]

    assert mock_get_batch_key.call_count == 4, "One for every entity"
    assert all([call_args.args[0] == resource for call_args in mock_get_batch_key.call_args_list])


@mock.patch("envoy.notification.crud.batch.get_batch_key")
@pytest.mark.parametrize("resource", [(r) for r in SubscriptionResource])
def test_AggregatorBatchedEntities_multi_batch(mock_get_batch_key: mock.MagicMock, resource: SubscriptionResource):
    """This completely isolates the batching algorithm from the use of get_batch_key / the underlying models"""

    fake_entity_1 = {"batch_key": (1, 2)}  # batch 1
    fake_entity_2 = {"batch_key": (1, 3)}  # batch 2
    fake_entity_3 = {"batch_key": (1, 2)}  # batch 1
    fake_entity_4 = {"batch_key": (2, 1)}  # batch 3

    mock_get_batch_key.side_effect = lambda r, m: m["batch_key"]

    ts = datetime(2024, 2, 2, 3, 4, 7)
    b = AggregatorBatchedEntities(ts, resource, [fake_entity_1, fake_entity_2, fake_entity_3, fake_entity_4])

    assert b.timestamp == ts
    assert len(b.models_by_batch_key) == 3
    assert b.models_by_batch_key[(1, 2)] == [fake_entity_1, fake_entity_3]
    assert b.models_by_batch_key[(1, 3)] == [fake_entity_2]
    assert b.models_by_batch_key[(2, 1)] == [fake_entity_4]

    assert mock_get_batch_key.call_count == 4, "One for every entity"
    assert all([call_args.args[0] == resource for call_args in mock_get_batch_key.call_args_list])


def test_get_batch_key_invalid():
    """Validates we raise our own custom exception"""
    with pytest.raises(NotificationError):
        get_batch_key(9999, generate_class_instance(Site))


@pytest.mark.parametrize(
    "resource,entity,expected",
    [
        (SubscriptionResource.SITE, Site(aggregator_id=1, site_id=2), (1, 2)),
        (
            SubscriptionResource.READING,
            SiteReading(
                site_reading_id=99,
                site_reading_type=SiteReadingType(aggregator_id=1, site_id=2, site_reading_type_id=3),
                site_reading_type_id=3,
            ),
            (1, 2, 3),
        ),
        (
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
            DynamicOperatingEnvelope(
                dynamic_operating_envelope_id=99,
                site_id=2,
                site=Site(site_id=2, aggregator_id=1),
            ),
            (1, 2),
        ),
        (
            SubscriptionResource.TARIFF_GENERATED_RATE,
            TariffGeneratedRate(
                tariff_generated_rate_id=99,
                site_id=3,
                tariff_id=2,
                start_time=datetime(2023, 2, 3, 4, 5, 6),
                site=Site(site_id=3, aggregator_id=1),
            ),
            (1, 2, 3, date(2023, 2, 3)),
        ),
        (
            SubscriptionResource.TARIFF_GENERATED_RATE,
            TariffGeneratedRate(
                tariff_generated_rate_id=99,
                site_id=3,
                tariff_id=2,
                start_time=datetime(2023, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
                site=Site(site_id=3, aggregator_id=1),
            ),
            (1, 2, 3, date(2023, 2, 3)),
        ),
    ],
)
def test_get_batch_key(resource: SubscriptionResource, entity: TResourceModel, expected: tuple):
    assert get_batch_key(resource, entity) == expected


def test_get_subscription_filter_id_invalid():
    """Validates we raise our own custom exception"""
    with pytest.raises(NotificationError):
        get_subscription_filter_id(9999, generate_class_instance(Site))


@pytest.mark.parametrize(
    "resource,entity,expected",
    [
        (SubscriptionResource.SITE, Site(aggregator_id=1, site_id=99), 99),
        (
            SubscriptionResource.READING,
            SiteReading(
                site_reading_id=99,
                site_reading_type_id=3,
            ),
            3,
        ),
        (
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
            DynamicOperatingEnvelope(
                dynamic_operating_envelope_id=99,
                site_id=2,
            ),
            99,
        ),
        (
            SubscriptionResource.TARIFF_GENERATED_RATE,
            TariffGeneratedRate(
                tariff_generated_rate_id=999,
                site_id=3,
                tariff_id=2,
                start_time=datetime(2023, 2, 3, 4, 5, 6),
            ),
            2,
        ),
    ],
)
def test_get_subscription_filter_id(resource: SubscriptionResource, entity: TResourceModel, expected: int):
    assert get_subscription_filter_id(resource, entity) == expected


def test_get_site_id_invalid():
    """Validates we raise our own custom exception"""
    with pytest.raises(NotificationError):
        get_site_id(9999, generate_class_instance(Site))


@pytest.mark.parametrize(
    "resource,entity,expected",
    [
        (SubscriptionResource.SITE, Site(aggregator_id=1, site_id=2), 2),
        (
            SubscriptionResource.READING,
            SiteReading(
                site_reading_id=99,
                site_reading_type=SiteReadingType(aggregator_id=1, site_id=2, site_reading_type_id=3),
                site_reading_type_id=3,
            ),
            2,
        ),
        (
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
            DynamicOperatingEnvelope(
                dynamic_operating_envelope_id=99,
                site_id=2,
            ),
            2,
        ),
        (
            SubscriptionResource.TARIFF_GENERATED_RATE,
            TariffGeneratedRate(
                tariff_generated_rate_id=99,
                site_id=3,
                tariff_id=2,
                start_time=datetime(2023, 2, 3, 4, 5, 6),
            ),
            3,
        ),
    ],
)
def test_get_site_id(resource: SubscriptionResource, entity: TResourceModel, expected: int):
    assert get_site_id(resource, entity) == expected


@pytest.mark.parametrize(
    "aggregator_id,resource,expected_sub_ids",
    [
        (1, SubscriptionResource.SITE, [1, 4]),
        (1, SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, [2]),
        (1, SubscriptionResource.READING, [5]),
        (2, SubscriptionResource.TARIFF_GENERATED_RATE, [3]),
        (1, SubscriptionResource.TARIFF_GENERATED_RATE, []),
        (99, SubscriptionResource.SITE, []),
        (2, SubscriptionResource.READING, []),
    ],
)
@pytest.mark.anyio
async def test_select_subscriptions_for_resource_filtering(
    pg_base_config, aggregator_id: int, resource: SubscriptionResource, expected_sub_ids: list[int]
):
    """Tests the filtering on select_subscriptions_for_resource"""
    async with generate_async_session(pg_base_config) as session:
        actual_entities = await select_subscriptions_for_resource(session, aggregator_id, resource)
        assert all([isinstance(e, Subscription) for e in actual_entities])
        assert [e.subscription_id for e in actual_entities] == expected_sub_ids


@pytest.mark.parametrize(
    "aggregator_id,resource,expected_conditions",
    [
        (
            1,
            SubscriptionResource.READING,
            [
                SubscriptionCondition(
                    subscription_condition_id=1,
                    subscription_id=5,
                    attribute=ConditionAttributeIdentifier.READING_VALUE,
                    lower_threshold=1,
                    upper_threshold=None,
                ),
                SubscriptionCondition(
                    subscription_condition_id=2,
                    subscription_id=5,
                    attribute=ConditionAttributeIdentifier.READING_VALUE,
                    lower_threshold=None,
                    upper_threshold=2,
                ),
            ],
        ),
        (1, SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, []),
    ],
)
@pytest.mark.anyio
async def test_select_subscriptions_for_resource_conditions(
    pg_base_config, aggregator_id: int, resource: SubscriptionResource, expected_conditions: list[SubscriptionCondition]
):
    """Tests that conditions are returned with the subscription"""
    async with generate_async_session(pg_base_config) as session:
        actual_entities = await select_subscriptions_for_resource(session, aggregator_id, resource)
        assert len(actual_entities) == 1

        assert all([isinstance(e, Subscription) for e in actual_entities])
        assert all([isinstance(c, SubscriptionCondition) for e in actual_entities for c in e.conditions])
        assert len(actual_entities[0].conditions) == len(expected_conditions)

        for i in range(len(expected_conditions)):
            assert_class_instance_equality(
                SubscriptionCondition, expected_conditions[i], actual_entities[0].conditions[i]
            )
