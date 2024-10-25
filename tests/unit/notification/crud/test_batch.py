import unittest.mock as mock
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier
from envoy_schema.server.schema.sep2.types import QualityFlagsType
from sqlalchemy import select

from envoy.notification.crud.batch import (
    AggregatorBatchedEntities,
    TResourceModel,
    fetch_der_availability_by_changed_at,
    fetch_der_rating_by_changed_at,
    fetch_der_setting_by_changed_at,
    fetch_der_status_by_changed_at,
    fetch_does_by_changed_at,
    fetch_rates_by_changed_at,
    fetch_readings_by_changed_at,
    fetch_sites_by_changed_at,
    get_batch_key,
    get_site_id,
    get_subscription_filter_id,
    select_subscriptions_for_resource,
)
from envoy.notification.exception import NotificationError
from envoy.server.crud.end_device import Site
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate


@pytest.mark.parametrize("resource", [(r) for r in SubscriptionResource])
def test_AggregatorBatchedEntities_empty(resource: SubscriptionResource):
    """Simple sanity check that empty lists dont crash out"""
    ts = datetime(2024, 1, 2, 3, 4, 5)
    b = AggregatorBatchedEntities(ts, resource, [])

    assert b.timestamp == ts
    assert len(b.models_by_batch_key) == 0
    assert b.total_entities == 0


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
    assert b.total_entities == 4
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
    assert b.total_entities == 4
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
        (
            SubscriptionResource.SITE_DER_AVAILABILITY,
            SiteDERAvailability(
                site_der_id=11,
                site_der_availability_id=22,
                site_der=SiteDER(
                    site_id=3,
                    site=Site(site_id=3, aggregator_id=1),
                ),
            ),
            (1, 3, PUBLIC_SITE_DER_ID),
        ),
        (
            SubscriptionResource.SITE_DER_RATING,
            SiteDERRating(
                site_der_id=11,
                site_der_rating_id=22,
                site_der=SiteDER(
                    site_id=3,
                    site=Site(site_id=3, aggregator_id=1),
                ),
            ),
            (1, 3, PUBLIC_SITE_DER_ID),
        ),
        (
            SubscriptionResource.SITE_DER_SETTING,
            SiteDERSetting(
                site_der_id=11,
                site_der_setting_id=22,
                site_der=SiteDER(
                    site_id=3,
                    site=Site(site_id=3, aggregator_id=1),
                ),
            ),
            (1, 3, PUBLIC_SITE_DER_ID),
        ),
        (
            SubscriptionResource.SITE_DER_STATUS,
            SiteDERStatus(
                site_der_id=11,
                site_der_status_id=22,
                site_der=SiteDER(
                    site_id=3,
                    site=Site(site_id=3, aggregator_id=1),
                ),
            ),
            (1, 3, PUBLIC_SITE_DER_ID),
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
                    upper_threshold=11,
                ),
                SubscriptionCondition(
                    subscription_condition_id=2,
                    subscription_id=5,
                    attribute=ConditionAttributeIdentifier.READING_VALUE,
                    lower_threshold=2,
                    upper_threshold=12,
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


@pytest.mark.parametrize(
    "timestamp,expected_sites",
    [
        (
            datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc),
            [
                Site(
                    site_id=1,
                    nmi="1111111111",
                    aggregator_id=1,
                    timezone_id="Australia/Brisbane",
                    created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    changed_time=datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc),
                    lfdi="site1-lfdi",
                    sfdi=1111,
                    device_category=0,
                ),
            ],
        ),
        (
            datetime(2022, 2, 3, 4, 5, 7),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_sites_by_timestamp(pg_base_config, timestamp: datetime, expected_sites: list[Site]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_sites_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_sites)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda site: site.site_id)

        assert all([isinstance(e, Site) for e in list_entities])
        for i in range(len(expected_sites)):
            assert_class_instance_equality(Site, expected_sites[i], list_entities[i])


@pytest.mark.anyio
async def test_fetch_sites_by_timestamp_multiple_aggs(pg_base_config):
    """Tests that entities are filtered/returned correctly and cover all aggregator ids"""

    timestamp = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)

    # start by setting all entities to a particular timestamp
    async with generate_async_session(pg_base_config) as session:
        all_entities_resp = await session.execute(select(Site))
        all_entities: Sequence[Site] = all_entities_resp.scalars().all()
        for e in all_entities:
            e.changed_time = timestamp
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_sites_by_changed_at(session, timestamp)
        assert batch.total_entities == len(all_entities)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda site: site.site_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4, 5, 6]) == set([e.site_id for e in list_entities])
        assert set([NULL_AGGREGATOR_ID, 1, 2]) == set(
            [e.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert empty_batch.total_entities == 0
        assert len(empty_batch.models_by_batch_key) == 0


@pytest.mark.parametrize(
    "timestamp,expected_rates",
    [
        (
            datetime(2022, 3, 4, 11, 22, 33, 500000, tzinfo=timezone.utc),
            [
                TariffGeneratedRate(
                    tariff_generated_rate_id=1,
                    tariff_id=1,
                    site_id=1,
                    calculation_log_id=2,
                    created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    changed_time=datetime(2022, 3, 4, 11, 22, 33, 500000, tzinfo=timezone.utc),
                    start_time=datetime(2022, 3, 5, 1, 2, 0, 0, tzinfo=timezone(timedelta(hours=10))),
                    duration_seconds=11,
                    import_active_price=Decimal("1.1"),
                    export_active_price=Decimal("-1.22"),
                    import_reactive_price=Decimal("1.333"),
                    export_reactive_price=Decimal("-1.4444"),
                ),
            ],
        ),
        (
            datetime(2022, 2, 3, 4, 5, 7),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_rates_by_timestamp(pg_base_config, timestamp: datetime, expected_rates: list[TariffGeneratedRate]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_rates_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_rates)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda rate: rate.tariff_generated_rate_id)

        assert all([isinstance(e, TariffGeneratedRate) for e in list_entities])
        for i in range(len(expected_rates)):
            assert_class_instance_equality(TariffGeneratedRate, expected_rates[i], list_entities[i])

        assert all([isinstance(e.site, Site) for e in list_entities]), "site relationship populated"
        assert all([e.site.site_id == e.site_id for e in list_entities]), "site relationship populated"
        assert all(
            [e.start_time.tzinfo == ZoneInfo(e.site.timezone_id) for e in list_entities]
        ), "start_time should be localized to the zone identified by the linked site"


@pytest.mark.anyio
async def test_fetch_rates_by_timestamp_multiple_aggs(pg_base_config):
    """Tests that entities are filtered/returned correctly and cover all aggregator ids"""

    timestamp = datetime(2024, 4, 6, 7, 8, 9, tzinfo=timezone.utc)

    # start by setting all entities to a particular timestamp
    async with generate_async_session(pg_base_config) as session:
        all_entities_resp = await session.execute(select(TariffGeneratedRate))
        all_entities: Sequence[TariffGeneratedRate] = all_entities_resp.scalars().all()
        for e in all_entities:
            e.changed_time = timestamp

        all_entities[-1].site_id = 3  # Move this price to aggregator 2
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_rates_by_changed_at(session, timestamp)
        assert batch.total_entities == len(all_entities)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda rate: rate.tariff_generated_rate_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4]) == set([e.tariff_generated_rate_id for e in list_entities])
        assert set([1, 2]) == set(
            [e.site.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_rates_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert empty_batch.total_entities == 0
        assert len(empty_batch.models_by_batch_key) == 0


@pytest.mark.parametrize(
    "timestamp,expected_does",
    [
        (
            datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc),
            [
                DynamicOperatingEnvelope(
                    dynamic_operating_envelope_id=1,
                    site_id=1,
                    calculation_log_id=2,
                    created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    changed_time=datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc),
                    start_time=datetime(2022, 5, 7, 1, 2, 0, 0, tzinfo=timezone(timedelta(hours=10))),
                    duration_seconds=11,
                    import_limit_active_watts=Decimal("1.11"),
                    export_limit_watts=Decimal("-1.22"),
                ),
            ],
        ),
        (
            datetime(2021, 2, 3, 4, 5, 7),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_does_by_timestamp(
    pg_base_config, timestamp: datetime, expected_does: list[DynamicOperatingEnvelope]
):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_does_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_does)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.dynamic_operating_envelope_id)

        assert all([isinstance(e, DynamicOperatingEnvelope) for e in list_entities])
        for i in range(len(expected_does)):
            assert_class_instance_equality(DynamicOperatingEnvelope, expected_does[i], list_entities[i])

        assert all([isinstance(e.site, Site) for e in list_entities]), "site relationship populated"
        assert all([e.site.site_id == e.site_id for e in list_entities]), "site relationship populated"
        assert all(
            [e.start_time.tzinfo == ZoneInfo(e.site.timezone_id) for e in list_entities]
        ), "start_time should be localized to the zone identified by the linked site"


@pytest.mark.anyio
async def test_fetch_does_by_timestamp_multiple_aggs(pg_base_config):
    """Tests that entities are filtered/returned correctly and cover all aggregator ids"""

    timestamp = datetime(2024, 1, 2, 7, 8, 9, tzinfo=timezone.utc)

    # start by setting all entities to a particular timestamp
    async with generate_async_session(pg_base_config) as session:
        all_entities_resp = await session.execute(select(DynamicOperatingEnvelope))
        all_entities: Sequence[DynamicOperatingEnvelope] = all_entities_resp.scalars().all()
        for e in all_entities:
            e.changed_time = timestamp

        all_entities[-1].site_id = 3  # Move this doe to aggregator 2
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_does_by_changed_at(session, timestamp)
        assert batch.total_entities == len(all_entities)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda rate: rate.dynamic_operating_envelope_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4]) == set([e.dynamic_operating_envelope_id for e in list_entities])
        assert set([1, 2]) == set(
            [e.site.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_does_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert empty_batch.total_entities == 0
        assert len(empty_batch.models_by_batch_key) == 0


@pytest.mark.parametrize(
    "timestamp,expected_readings",
    [
        (
            datetime(2022, 6, 7, 11, 22, 33, 500000, tzinfo=timezone.utc),
            [
                SiteReading(
                    site_reading_id=1,
                    site_reading_type_id=1,
                    created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    changed_time=datetime(2022, 6, 7, 11, 22, 33, 500000, tzinfo=timezone.utc),
                    local_id=11111,
                    quality_flags=QualityFlagsType.VALID,
                    time_period_start=datetime(2022, 6, 7, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=10))),
                    time_period_seconds=300,
                    value=11,
                ),
            ],
        ),
        (
            datetime(2021, 2, 3, 4, 5, 7),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_readings_by_timestamp(pg_base_config, timestamp: datetime, expected_readings: list[SiteReading]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_readings_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_readings)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda reading: reading.site_reading_id)

        assert all([isinstance(e, SiteReading) for e in list_entities])
        for i in range(len(expected_readings)):
            assert_class_instance_equality(SiteReading, expected_readings[i], list_entities[i])

        assert all(
            [isinstance(e.site_reading_type, SiteReadingType) for e in list_entities]
        ), "site_reading_type relationship populated"
        assert all(
            [e.site_reading_type.site_reading_type_id == e.site_reading_type_id for e in list_entities]
        ), "site_reading_type relationship populated"


@pytest.mark.anyio
async def test_fetch_readings_by_timestamp_multiple_aggs(pg_base_config):
    """Tests that entities are filtered/returned correctly and cover all aggregator ids"""

    timestamp = datetime(2021, 1, 2, 7, 8, 9, tzinfo=timezone.utc)

    # start by setting all entities to a particular timestamp
    async with generate_async_session(pg_base_config) as session:
        all_entities_resp = await session.execute(select(SiteReading))
        all_entities: Sequence[SiteReading] = all_entities_resp.scalars().all()
        for e in all_entities:
            e.changed_time = timestamp

        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_readings_by_changed_at(session, timestamp)
        assert batch.total_entities == len(all_entities)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda reading: reading.site_reading_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4]) == set([e.site_reading_id for e in list_entities])
        assert set([1, 3]) == set(
            [e.site_reading_type.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_readings_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert empty_batch.total_entities == 0
        assert len(empty_batch.models_by_batch_key) == 0


@pytest.mark.parametrize(
    "timestamp,expected_ids",
    [
        (
            datetime(2022, 7, 23, 10, 3, 23, 500000, tzinfo=timezone.utc),
            [1],
        ),
        (
            datetime(2021, 2, 3, 4, 5, 7),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_der_availability_by_timestamp(pg_base_config, timestamp: datetime, expected_ids: list[int]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_availability_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_ids)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_availability_id)

        assert all([isinstance(e, SiteDERAvailability) for e in list_entities])
        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_availability_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.parametrize(
    "timestamp,expected_ids",
    [
        (
            datetime(2022, 4, 13, 10, 1, 42, 500000, tzinfo=timezone.utc),
            [1],
        ),
        (
            datetime(2022, 2, 3, 4, 5, 7),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_der_rating_by_timestamp(pg_base_config, timestamp: datetime, expected_ids: list[int]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_rating_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_ids)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_rating_id)

        assert all([isinstance(e, SiteDERRating) for e in list_entities])
        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_rating_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.parametrize(
    "timestamp,expected_ids",
    [
        (
            datetime(2022, 2, 9, 11, 6, 44, 500000, tzinfo=timezone.utc),
            [1],
        ),
        (
            datetime(2022, 2, 3, 4, 5, 8),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_der_setting_by_timestamp(pg_base_config, timestamp: datetime, expected_ids: list[int]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_setting_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_ids)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_setting_id)

        assert all([isinstance(e, SiteDERSetting) for e in list_entities])
        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_setting_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.parametrize(
    "timestamp,expected_ids",
    [
        (
            datetime(2022, 11, 1, 11, 5, 4, 500000, tzinfo=timezone.utc),
            [1],
        ),
        (
            datetime(2022, 2, 3, 4, 5, 8),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_der_status_by_timestamp(pg_base_config, timestamp: datetime, expected_ids: list[int]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_status_by_changed_at(session, timestamp)
        assert batch.total_entities == len(expected_ids)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_status_id)

        assert all([isinstance(e, SiteDERStatus) for e in list_entities])
        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_status_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"
