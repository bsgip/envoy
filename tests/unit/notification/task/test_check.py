import unittest.mock as mock
from uuid import UUID

import pytest
from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier

from envoy.notification.task.check import (
    NotificationEntities,
    batched,
    entities_serviced_by_subscription,
    get_entity_pages,
)
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate


@pytest.mark.parametrize(
    "input, size, expected",
    [
        # most edge cases
        ([1, 2, 3, 4, 5], 2, [[1, 2], [3, 4], [5]]),
        ([1, 2, 3, 4, 5], 3, [[1, 2, 3], [4, 5]]),
        ([1, 2, 3, 4, 5], 5, [[1, 2, 3, 4, 5]]),
        ([1, 2, 3, 4, 5], 10, [[1, 2, 3, 4, 5]]),
        ([1, 2, 3, 4, 5], 1, [[1], [2], [3], [4], [5]]),
        ([1, 2, 3, 4], 2, [[1, 2], [3, 4]]),
        ([], 2, []),
        ([], 1, []),
        # testing with other types
        (["one", None, {"three": 3}, "", "5"], 2, [["one", None], [{"three": 3}, ""], ["5"]]),
    ],
)
def test_batched(input: list, size: int, expected: list[list]):
    actual = list(batched(input, size))
    assert expected == actual


@mock.patch("envoy.notification.task.check.batched")
def test_get_entity_pages_basic(mock_batched: mock.MagicMock):
    """This relies on the unit tests for batched to ensure the batching is correct"""
    sub = Subscription()
    batch_key = (1, 2, "three")
    resource = SubscriptionResource.SITE
    page_size = 999
    entities = [Site(site_id=1), Site(site_id=2), Site(site_id=3)]

    mock_batched.return_value = [[entities[0], entities[1]], [entities[2]]]

    actual = list(get_entity_pages(resource, sub, batch_key, page_size, entities))
    assert len(actual) == 2, "Our mock batch is returned as 2 pages"
    assert all([isinstance(ne, NotificationEntities) for ne in actual])

    assert actual[0].entities == [entities[0], entities[1]]
    assert actual[0].subscription is sub
    assert actual[0].batch_key == batch_key
    assert actual[0].pricing_reading_type is None

    assert actual[1].entities == [entities[2]]
    assert actual[1].subscription is sub
    assert actual[1].batch_key == batch_key
    assert actual[1].pricing_reading_type is None

    assert actual[0].notification_id != actual[1].notification_id, "Each notification should have a unique ID"

    mock_batched.assert_called_once_with(entities, page_size)


@mock.patch("envoy.notification.task.check.batched")
def test_get_entity_pages_rates(mock_batched: mock.MagicMock):
    """Similar to test_get_entity_pages_basic but tests the special case of rates multiplying the pages out for
    each PricingReadingType"""
    sub = Subscription()
    batch_key = (1, 2, "three")
    resource = SubscriptionResource.TARIFF_GENERATED_RATE
    page_size = 999
    entities = [
        TariffGeneratedRate(tariff_generated_rate_id=1),
        TariffGeneratedRate(tariff_generated_rate_id=2),
        TariffGeneratedRate(tariff_generated_rate_id=3),
    ]

    mock_batched.return_value = [[entities[0], entities[1]], [entities[2]]]

    actual = list(get_entity_pages(resource, sub, batch_key, page_size, entities))
    assert len(actual) == 8, "Our mock batch is returned as 2 pages which then multiply out 4 price types"
    assert all([isinstance(ne, NotificationEntities) for ne in actual])

    for prt in PricingReadingType:
        prt_pages = [p for p in actual if p.pricing_reading_type == prt]
        assert len(prt_pages) == 2, f"Expected to find two pages for pricing_reading_type {prt}"

        assert prt_pages[0].entities == [entities[0], entities[1]]
        assert prt_pages[0].subscription is sub
        assert prt_pages[0].batch_key == batch_key
        assert prt_pages[0].pricing_reading_type == prt

        assert prt_pages[1].entities == [entities[2]]
        assert prt_pages[1].subscription is sub
        assert prt_pages[1].batch_key == batch_key
        assert prt_pages[1].pricing_reading_type == prt

    assert len(set([p.notification_id for p in actual])) == len(actual), "Each notification_id should be unique"

    # Ensure all the calls to batched are made with the appropriate args
    assert all([args.args == (entities, page_size) for args in mock_batched.call_args_list])


@pytest.mark.parametrize(
    "sub, resource, entities, expected_passing_entity_indexes",
    [
        #
        # No restriction - get everything
        #
        (
            Subscription(resource_type=SubscriptionResource.SITE, conditions=[]),
            SubscriptionResource.SITE,
            [Site(site_id=1), Site(site_id=2)],
            [0, 1],
        ),
        #
        # Site filtering
        #
        (
            Subscription(resource_type=SubscriptionResource.SITE, scoped_site_id=2, conditions=[]),
            SubscriptionResource.SITE,
            [Site(site_id=2), Site(site_id=1), Site(site_id=2), Site(site_id=3)],
            [0, 2],
        ),
        (
            Subscription(resource_type=SubscriptionResource.READING, scoped_site_id=2, conditions=[]),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, site_reading_type_id=2, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, site_reading_type_id=1, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, site_reading_type_id=2, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, site_reading_type_id=1, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [0, 1],
        ),
        #
        # resource ID filtering
        #
        (
            Subscription(resource_type=SubscriptionResource.SITE, resource_id=2, conditions=[]),
            SubscriptionResource.SITE,
            [Site(site_id=2), Site(site_id=1), Site(site_id=2), Site(site_id=3)],
            [0, 2],
        ),
        (
            Subscription(resource_type=SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, resource_id=2, conditions=[]),
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
            [
                DynamicOperatingEnvelope(dynamic_operating_envelope_id=1, site_id=2),
                DynamicOperatingEnvelope(dynamic_operating_envelope_id=2, site_id=2),
            ],
            [1],
        ),
        (
            Subscription(resource_type=SubscriptionResource.TARIFF_GENERATED_RATE, resource_id=2, conditions=[]),
            SubscriptionResource.TARIFF_GENERATED_RATE,
            [
                TariffGeneratedRate(tariff_generated_rate_id=1, site_id=2, tariff_id=2),
                TariffGeneratedRate(tariff_generated_rate_id=2, site_id=2, tariff_id=1),
                TariffGeneratedRate(tariff_generated_rate_id=3, site_id=1, tariff_id=2),
                TariffGeneratedRate(tariff_generated_rate_id=4, site_id=1, tariff_id=1),
            ],
            [0, 2],
        ),
        (
            Subscription(resource_type=SubscriptionResource.READING, resource_id=2, conditions=[]),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, site_reading_type_id=2, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, site_reading_type_id=1, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, site_reading_type_id=2, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, site_reading_type_id=1, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [0, 2],
        ),
        #
        # Combo resource/site id filtering
        #
        (
            Subscription(resource_type=SubscriptionResource.READING, resource_id=2, scoped_site_id=2, conditions=[]),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, site_reading_type_id=2, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, site_reading_type_id=1, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, site_reading_type_id=2, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, site_reading_type_id=1, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [0],
        ),
        #
        # Conditions
        #
        (
            Subscription(
                resource_type=SubscriptionResource.READING,
                conditions=[SubscriptionCondition(attribute=ConditionAttributeIdentifier.READING_VALUE)],
            ),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, value=-10, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, value=-15, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, value=20, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, value=25, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [0, 1, 2, 3],
        ),
        (
            Subscription(
                resource_type=SubscriptionResource.READING,
                conditions=[
                    SubscriptionCondition(attribute=ConditionAttributeIdentifier.READING_VALUE, lower_threshold=20)
                ],
            ),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, value=-10, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, value=-15, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, value=20, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, value=25, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [0, 1],
        ),
        (
            Subscription(
                resource_type=SubscriptionResource.READING,
                conditions=[
                    SubscriptionCondition(attribute=ConditionAttributeIdentifier.READING_VALUE, upper_threshold=20)
                ],
            ),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, value=-10, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, value=-15, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, value=20, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, value=25, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [3],
        ),
        (
            Subscription(
                resource_type=SubscriptionResource.READING,
                conditions=[
                    SubscriptionCondition(
                        attribute=ConditionAttributeIdentifier.READING_VALUE, lower_threshold=-10, upper_threshold=20
                    )
                ],
            ),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, value=-10, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, value=-15, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, value=20, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, value=25, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [1, 3],
        ),
        # Splitting the conditions is not equivalent to having them as a single combo
        # it's impossible to satisfy the two conditions simultaneously
        (
            Subscription(
                resource_type=SubscriptionResource.READING,
                conditions=[
                    SubscriptionCondition(attribute=ConditionAttributeIdentifier.READING_VALUE, upper_threshold=20),
                    SubscriptionCondition(attribute=ConditionAttributeIdentifier.READING_VALUE, lower_threshold=-10),
                ],
            ),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, value=-10, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, value=-15, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, value=20, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, value=25, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [],
        ),
        # Contrived combo of conditions - first condition will always match - second only matches some
        (
            Subscription(
                resource_type=SubscriptionResource.READING,
                conditions=[
                    SubscriptionCondition(
                        attribute=ConditionAttributeIdentifier.READING_VALUE, lower_threshold=100, upper_threshold=-100
                    ),
                    SubscriptionCondition(
                        attribute=ConditionAttributeIdentifier.READING_VALUE, lower_threshold=-10, upper_threshold=20
                    ),
                ],
            ),
            SubscriptionResource.READING,
            [
                SiteReading(site_reading_id=1, value=-10, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=2, value=-15, site_reading_type=SiteReadingType(site_id=2)),
                SiteReading(site_reading_id=3, value=20, site_reading_type=SiteReadingType(site_id=1)),
                SiteReading(site_reading_id=4, value=25, site_reading_type=SiteReadingType(site_id=1)),
            ],
            [1, 3],
        ),
        #
        # Ensure subscription type matches
        #
        (
            Subscription(resource_type=SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, conditions=[]),
            SubscriptionResource.SITE,
            [Site(site_id=1), Site(site_id=2)],
            [],
        ),
    ],
)
def test_entities_serviced_by_subscription(
    sub: Subscription, resource: SubscriptionResource, entities: list, expected_passing_entity_indexes: list[int]
):
    """Stress tests the various ways we can filter entities from matching a subscription"""
    actual = [e for e in entities_serviced_by_subscription(sub, resource, entities)]
    expected = [entities[i] for i in expected_passing_entity_indexes]

    assert actual == expected
