import unittest.mock as mock
from datetime import datetime, timezone
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.pub_sub import (
    ConditionAttributeIdentifier,
    Notification,
    NotificationResourceCombined,
)

from envoy.notification.crud.batch import AggregatorBatchedEntities, get_batch_key
from envoy.notification.exception import NotificationError
from envoy.notification.task.check import (
    DER_RESOURCES,
    NotificationEntities,
    batched,
    check_db_upsert,
    entities_serviced_by_subscription,
    entities_to_notification,
    fetch_batched_entities,
    get_entity_pages,
)
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import PRICE_DECIMAL_POWER, TariffGeneratedRate
from tests.unit.notification.mocks import (
    assert_task_kicked_n_times,
    assert_task_kicked_with_broker_and_args,
    configure_mock_task,
    create_mock_broker,
    get_mock_task_kicker_call_args,
)


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
    "resource",
    [
        SubscriptionResource.SITE_DER_AVAILABILITY,
        SubscriptionResource.SITE_DER_RATING,
        SubscriptionResource.SITE_DER_SETTING,
        SubscriptionResource.SITE_DER_STATUS,
    ],
)
def test_get_entity_pages_der(resource: SubscriptionResource):
    """Similar to test_get_entity_pages_basic but tests the special case of rates multiplying the pages out for
    each PricingReadingType"""
    sub = Subscription()
    batch_key = (1, 2, "three")
    page_size = 999
    entities = [
        SiteDERStatus(site_der_status_id=1),
        SiteDERStatus(site_der_status_id=2),
        SiteDERStatus(site_der_status_id=3),
    ]

    actual = list(get_entity_pages(resource, sub, batch_key, page_size, entities))
    assert len(actual) == len(entities), "We expect 3 single entities for DER resources"
    assert all([isinstance(ne, NotificationEntities) for ne in actual])

    # We expect 3 notifications - each with a single entity
    assert all([len(n.entities) == 1 for n in actual])
    assert [e.site_der_status_id for n in actual for e in n.entities] == [1, 2, 3]


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
        (
            Subscription(
                resource_type=SubscriptionResource.SITE_DER_STATUS, resource_id=PUBLIC_SITE_DER_ID, conditions=[]
            ),
            SubscriptionResource.SITE_DER_STATUS,
            [SiteDERStatus(site_der_status_id=3), SiteDERStatus(site_der_status_id=4)],
            [0, 1],  # DER uses a fixed site_der_id value
        ),
        (
            Subscription(
                resource_type=SubscriptionResource.SITE_DER_STATUS, resource_id=PUBLIC_SITE_DER_ID + 1, conditions=[]
            ),
            SubscriptionResource.SITE_DER_STATUS,
            [SiteDERStatus(site_der_status_id=3), SiteDERStatus(site_der_status_id=4)],
            [],  # DER uses a fixed site_der_id value
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


def test_entities_to_notification_unknown_resource():
    """We catch bad SubscriptionResource with our own error"""
    with pytest.raises(NotificationError):
        entities_to_notification(9999, Subscription(resource_type=9999), (1, 2, 3), None, [], None)


@pytest.mark.parametrize(
    "resource, entity_class",
    [
        (SubscriptionResource.SITE, Site),
        (SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, DynamicOperatingEnvelope),
        (SubscriptionResource.READING, SiteReading),
        (SubscriptionResource.TARIFF_GENERATED_RATE, TariffGeneratedRate),
        (SubscriptionResource.SITE_DER_AVAILABILITY, SiteDERAvailability),
        (SubscriptionResource.SITE_DER_RATING, SiteDERRating),
        (SubscriptionResource.SITE_DER_SETTING, SiteDERSetting),
        (SubscriptionResource.SITE_DER_STATUS, SiteDERStatus),
    ],
)
def test_entities_to_notification_sites(resource: SubscriptionResource, entity_class: type):
    """For every resource/type mapping - generate a notification and do some cursory examination of the
    resulting notification - the majority of the test are captured in the mapper unit tests - this is here
    to catch parameter errors / other simple issues"""
    href_prefix = "/my_href/prefix"
    sub = Subscription(resource_type=resource, notification_uri="http://example.com/foo")
    pricing_reading_type = (
        PricingReadingType.EXPORT_ACTIVE_POWER_KWH if resource == SubscriptionResource.TARIFF_GENERATED_RATE else None
    )
    batch_key = get_batch_key(resource, generate_class_instance(entity_class, generate_relationships=True))

    # Try for various lengths (empty, singular, many)
    for entity_length in [0, 1, 3]:
        entities = []
        for i in range(entity_length):
            # Generate test instances - tweaking them if the generated values fall foul of pydantic range validation
            e = generate_class_instance(entity_class, seed=i, generate_relationships=True)
            if isinstance(e, SiteDERStatus):
                cast(SiteDERStatus, e).state_of_charge_status = i
            entities.append(e)

        notification = entities_to_notification(resource, sub, batch_key, href_prefix, entities, pricing_reading_type)
        assert isinstance(notification, Notification)
        assert notification.subscribedResource.startswith(href_prefix)
        assert notification.subscriptionURI.startswith(href_prefix)
        assert "{" not in notification.subscribedResource, "Trying to catch format variables not being replaced"
        assert "{" not in notification.subscriptionURI, "Trying to catch format variables not being replaced"

        # DER resources are NOT list enabled and either set resource with the first element or leave it None
        if resource in DER_RESOURCES:
            if entity_length > 0:
                assert isinstance(notification.resource, NotificationResourceCombined)
                assert notification.resource.all_ is None
                assert notification.resource.results is None
            else:
                assert notification.resource is None
        else:
            assert notification.resource.all_ == len(entities)
            assert notification.resource.results == len(entities)
            assert isinstance(notification.resource, NotificationResourceCombined)

        if resource == SubscriptionResource.SITE:
            assert len(notification.resource.EndDevice) == len(entities)
        elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
            assert len(notification.resource.DERControl) == len(entities)
        elif resource == SubscriptionResource.READING:
            assert len(notification.resource.Readings) == len(entities)
        elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
            assert len(notification.resource.TimeTariffInterval) == len(entities)
        elif resource == SubscriptionResource.SITE_DER_AVAILABILITY and entity_length:
            assert notification.resource.statWAvail.value == entities[0].estimated_w_avail_value
        elif resource == SubscriptionResource.SITE_DER_RATING and entity_length:
            assert notification.resource.doeModesSupported == entities[0].doe_modes_supported
        elif resource == SubscriptionResource.SITE_DER_SETTING and entity_length:
            assert notification.resource.doeModesEnabled == entities[0].doe_modes_enabled
        elif resource == SubscriptionResource.SITE_DER_STATUS and entity_length:
            assert notification.resource.inverterStatus.value == entities[0].inverter_status


@pytest.mark.anyio
async def test_fetch_batched_entities_bad_resource():
    mock_session = create_mock_session()
    with pytest.raises(NotificationError):
        await fetch_batched_entities(mock_session, 9999, datetime.now())
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.notification.task.check.transmit_notification")
@mock.patch("envoy.notification.task.check.entities_serviced_by_subscription")
@mock.patch("envoy.notification.task.check.select_subscriptions_for_resource")
@mock.patch("envoy.notification.task.check.fetch_batched_entities")
async def test_check_db_upsert(
    mock_fetch_batched_entities: mock.MagicMock,
    mock_select_subscriptions_for_resource: mock.MagicMock,
    mock_entities_serviced_by_subscription: mock.MagicMock,
    mock_transmit_notification: mock.MagicMock,
):
    """Runs through the bulk of check_db_upsert to ensure that the expected notifications are raised"""

    #
    # ARRANGE
    #

    configure_mock_task(mock_transmit_notification)

    mock_session = create_mock_session()
    mock_broker = create_mock_broker()
    href_prefix = "/href/prefix"
    resource = SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE
    timestamp = datetime(2023, 2, 3, 4, 5, 6, tzinfo=timezone.utc)

    # Create some entities that will form 2 batches
    batch1_entity1: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=101, generate_relationships=True
    )
    batch1_entity2: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=202, generate_relationships=True
    )
    batch2_entity1: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=303, generate_relationships=True
    )
    batch1_entity2.site_id = batch1_entity1.site_id
    batch1_entity2.site.site_id = batch1_entity1.site.site_id
    batch1_entity2.site.aggregator_id = batch1_entity1.site.aggregator_id
    entities = AggregatorBatchedEntities(timestamp, resource, [batch1_entity1, batch1_entity2, batch2_entity1])
    mock_fetch_batched_entities.return_value = entities

    # Create some subscriptions for the two aggregators we implied above
    agg1_sub1: Subscription = generate_class_instance(Subscription, seed=11)  # Matches nothing
    agg1_sub2: Subscription = generate_class_instance(Subscription, seed=22)
    agg2_sub1: Subscription = generate_class_instance(Subscription, seed=33)
    mock_select_subscriptions_for_resource.side_effect = lambda session, agg_id, resource: (
        [agg1_sub1, agg1_sub2] if agg_id == batch1_entity1.site.aggregator_id else [agg2_sub1]
    )

    # Configure what entities are serviced by what subscription
    # agg1_sub1 will match nothing but all other subs will match every entity
    def side_effect_entities_serviced_by_subscription(sub, resource, entities):
        if sub is agg1_sub1:
            return (e for e in [])
        else:
            return (e for e in entities)

    mock_entities_serviced_by_subscription.side_effect = side_effect_entities_serviced_by_subscription

    #
    # ACT
    #
    await check_db_upsert(
        session=mock_session,
        broker=mock_broker,
        href_prefix=href_prefix,
        resource=resource,
        timestamp_epoch=timestamp.timestamp(),
    )

    #
    # ASSERT
    #

    # There should be 2 notifications sent out (as one of the subscriptions match no entities)
    assert_task_kicked_n_times(mock_transmit_notification, 2)
    assert_task_kicked_with_broker_and_args(
        mock_transmit_notification, mock_broker, remote_uri=agg1_sub2.notification_uri, attempt=0
    )
    assert_task_kicked_with_broker_and_args(
        mock_transmit_notification, mock_broker, remote_uri=agg2_sub1.notification_uri, attempt=0
    )

    mock_fetch_batched_entities.assert_called_once_with(mock_session, resource, timestamp)

    # Subscriptions should only be fetched ONCE for each aggregator
    assert mock_select_subscriptions_for_resource.call_count == 2
    assert (mock_session, batch1_entity1.site.aggregator_id, resource) in [
        ca.args for ca in mock_select_subscriptions_for_resource.call_args_list
    ]
    assert (mock_session, batch2_entity1.site.aggregator_id, resource) in [
        ca.args for ca in mock_select_subscriptions_for_resource.call_args_list
    ]

    # No need to commit - persistence is handled via kicking off to transmit_notification
    # All DB interactions should be readonly
    assert_mock_session(mock_session, committed=False)

    # Do a slightly deeper dive on the content/notifications being transmitted
    kiq_args = get_mock_task_kicker_call_args(mock_transmit_notification)
    all_content: list[str] = [a.kwargs["content"] for a in kiq_args]
    assert all([isinstance(c, str) for c in all_content])
    assert len(set([c for c in all_content])) == len(all_content), "All content must be unique"

    # See if our entities appear in the output content (use the timestamp as unique fingerprint)
    batch1_entity1_fingerprint = f"<start>{str(int(batch1_entity1.start_time.timestamp()))}</start>"
    batch1_entity2_fingerprint = f"<start>{str(int(batch1_entity2.start_time.timestamp()))}</start>"
    batch2_entity1_fingerprint = f"<start>{str(int(batch2_entity1.start_time.timestamp()))}</start>"
    assert batch1_entity1_fingerprint in all_content[0]
    assert batch1_entity2_fingerprint in all_content[0]
    assert batch2_entity1_fingerprint not in all_content[0]
    assert batch1_entity1_fingerprint not in all_content[1]
    assert batch1_entity2_fingerprint not in all_content[1]
    assert batch2_entity1_fingerprint in all_content[1]

    all_ids: list[str] = [a.kwargs["notification_id"] for a in kiq_args]
    assert all([isinstance(id, str) for id in all_ids])
    assert len(set([c for c in all_ids])) == len(all_ids), "All notification_id should be unique"


@pytest.mark.anyio
@mock.patch("envoy.notification.task.check.transmit_notification")
@mock.patch("envoy.notification.task.check.entities_serviced_by_subscription")
@mock.patch("envoy.notification.task.check.select_subscriptions_for_resource")
@mock.patch("envoy.notification.task.check.fetch_batched_entities")
async def test_check_db_upsert_rates(
    mock_fetch_batched_entities: mock.MagicMock,
    mock_select_subscriptions_for_resource: mock.MagicMock,
    mock_entities_serviced_by_subscription: mock.MagicMock,
    mock_transmit_notification: mock.MagicMock,
):
    """Runs through the bulk of check_db_upsert to ensure that the expected notifications are raised"""

    #
    # ARRANGE
    #

    configure_mock_task(mock_transmit_notification)

    mock_session = create_mock_session()
    mock_broker = create_mock_broker()
    href_prefix = "/href/prefix"
    resource = SubscriptionResource.TARIFF_GENERATED_RATE
    timestamp = datetime(2023, 2, 3, 4, 5, 6, tzinfo=timezone.utc)

    # Create some entities that will form 2 batches
    rate1: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate, seed=101, generate_relationships=True)
    rate2: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate, seed=202, generate_relationships=True)
    rate2.site_id = rate1.site_id
    rate2.tariff_id = rate1.tariff_id
    rate2.site.site_id = rate1.site.site_id
    rate2.site.aggregator_id = rate1.site.aggregator_id

    rate1.start_time = datetime(2022, 4, 6, 14, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane"))
    rate2.start_time = datetime(2022, 4, 6, 14, 5, 0, tzinfo=ZoneInfo("Australia/Brisbane"))
    entities = AggregatorBatchedEntities(timestamp, resource, [rate1, rate2])
    mock_fetch_batched_entities.return_value = entities

    # Create a single sub
    sub1: Subscription = generate_class_instance(Subscription, seed=11)
    mock_select_subscriptions_for_resource.return_value = [sub1]

    # Configure what entities are serviced by what subscription
    mock_entities_serviced_by_subscription.return_value = (e for e in [rate1, rate2])

    #
    # ACT
    #
    await check_db_upsert(
        session=mock_session,
        broker=mock_broker,
        href_prefix=href_prefix,
        resource=resource,
        timestamp_epoch=timestamp.timestamp(),
    )

    #
    # ASSERT
    #

    # There should be 4 notifications sent out - each containing 2 rates (one for every price type)
    assert_task_kicked_n_times(mock_transmit_notification, 4)
    assert_task_kicked_with_broker_and_args(
        mock_transmit_notification, mock_broker, remote_uri=sub1.notification_uri, attempt=0
    )

    mock_fetch_batched_entities.assert_called_once_with(mock_session, resource, timestamp)

    # Subscriptions should only be fetched ONCE for each aggregator
    mock_select_subscriptions_for_resource.assert_called_once_with(mock_session, rate1.site.aggregator_id, resource)

    # No need to commit - persistence is handled via kicking off to transmit_notification
    # All DB interactions should be readonly
    assert_mock_session(mock_session, committed=False)

    # Do a slightly deeper dive on the content/notifications being transmitted
    kiq_args = get_mock_task_kicker_call_args(mock_transmit_notification)
    all_content: list[str] = [a.kwargs["content"] for a in kiq_args]
    assert all([isinstance(c, str) for c in all_content])
    assert len(set([c for c in all_content])) == len(all_content), "All content must be unique"

    # See if our entities appear in the output content (use the timestamp as unique fingerprint)
    rate1_export_active_fingerprint = f"14:00/cti/{rate1.export_active_price * PRICE_DECIMAL_POWER}"
    rate1_import_active_fingerprint = f"14:00/cti/{rate1.import_active_price * PRICE_DECIMAL_POWER}"
    rate1_export_reactive_fingerprint = f"14:00/cti/{rate1.export_reactive_price * PRICE_DECIMAL_POWER}"
    rate1_import_reactive_fingerprint = f"14:00/cti/{rate1.import_reactive_price * PRICE_DECIMAL_POWER}"
    rate2_export_active_fingerprint = f"14:05/cti/{rate2.export_active_price * PRICE_DECIMAL_POWER}"
    rate2_import_active_fingerprint = f"14:05/cti/{rate2.import_active_price * PRICE_DECIMAL_POWER}"
    rate2_export_reactive_fingerprint = f"14:05/cti/{rate2.export_reactive_price * PRICE_DECIMAL_POWER}"
    rate2_import_reactive_fingerprint = f"14:05/cti/{rate2.import_reactive_price * PRICE_DECIMAL_POWER}"

    assert (
        len([c for c in all_content if rate1_export_active_fingerprint in c and rate2_export_active_fingerprint in c])
        == 1
    )
    assert (
        len([c for c in all_content if rate1_import_active_fingerprint in c and rate2_import_active_fingerprint in c])
        == 1
    )
    assert (
        len(
            [
                c
                for c in all_content
                if rate1_export_reactive_fingerprint in c and rate2_export_reactive_fingerprint in c
            ]
        )
        == 1
    )
    assert (
        len(
            [
                c
                for c in all_content
                if rate1_import_reactive_fingerprint in c and rate2_import_reactive_fingerprint in c
            ]
        )
        == 1
    )

    all_ids: list[str] = [a.kwargs["notification_id"] for a in kiq_args]
    assert all([isinstance(id, str) for id in all_ids])
    assert len(set([c for c in all_ids])) == len(all_ids), "All notification_id should be unique"
