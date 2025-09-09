import unittest.mock as mock
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_dict_type, assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier
from envoy_schema.server.schema.sep2.types import QualityFlagsType
from sqlalchemy import select

from envoy.notification.crud.batch import (
    AggregatorBatchedEntities,
    fetch_default_site_controls_by_changed_at,
    fetch_der_availability_by_changed_at,
    fetch_der_rating_by_changed_at,
    fetch_der_setting_by_changed_at,
    fetch_der_status_by_changed_at,
    fetch_does_by_changed_at,
    fetch_rates_by_changed_at,
    fetch_readings_by_changed_at,
    fetch_runtime_config_by_changed_at,
    fetch_site_control_groups_by_changed_at,
    fetch_sites_by_changed_at,
    get_batch_key,
    get_site_id,
    get_subscription_filter_id,
    select_subscriptions_for_resource,
)
from envoy.notification.crud.common import (
    ArchiveControlGroupScopedDefaultSiteControl,
    ArchiveSiteScopedRuntimeServerConfig,
    ArchiveSiteScopedSiteControlGroup,
    ControlGroupScopedDefaultSiteControl,
    SiteScopedRuntimeServerConfig,
    SiteScopedSiteControlGroup,
    TResourceModel,
)
from envoy.notification.exception import NotificationError
from envoy.server.crud.site import Site
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope, ArchiveSiteControlGroup
from envoy.server.model.archive.site import (
    ArchiveDefaultSiteControl,
    ArchiveSite,
    ArchiveSiteDER,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.base import Base
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup
from envoy.server.model.server import RuntimeServerConfig
from envoy.server.model.site import (
    DefaultSiteControl,
    SiteDER,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
)
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate


def assert_batched_entities(
    batch: AggregatorBatchedEntities,
    expected_model_type: type[Base],
    expected_deleted_type: type[ArchiveBase],
    expected_model_count: int,
    expected_deleted_count: int,
):

    assert isinstance(batch, AggregatorBatchedEntities)
    assert_dict_type(tuple, list, batch.models_by_batch_key)
    assert_dict_type(tuple, list, batch.deleted_by_batch_key)
    for v in batch.models_by_batch_key.values():
        assert_list_type(expected_model_type, v)
    for v in batch.deleted_by_batch_key.values():
        assert_list_type(expected_deleted_type, v)

    assert sum(len(v) for v in batch.models_by_batch_key.values()) == expected_model_count
    assert sum(len(v) for v in batch.deleted_by_batch_key.values()) == expected_deleted_count


@pytest.mark.parametrize("resource", [(r) for r in SubscriptionResource])
def test_AggregatorBatchedEntities_empty(resource: SubscriptionResource):
    """Simple sanity check that empty lists dont crash out"""
    ts = datetime(2024, 1, 2, 3, 4, 5)
    b = AggregatorBatchedEntities(ts, resource, [], [])

    assert b.timestamp == ts
    assert len(b.models_by_batch_key) == 0
    assert_batched_entities(b, Base, ArchiveBase, 0, 0)


@mock.patch("envoy.notification.crud.batch.get_batch_key")
@pytest.mark.parametrize("resource", [(r) for r in SubscriptionResource])
def test_AggregatorBatchedEntities_single_batch(mock_get_batch_key: mock.MagicMock, resource: SubscriptionResource):
    """This completely isolates the batching algorithm from the use of get_batch_key / the underlying models"""

    # Everything in this test will be a single batch
    fake_entity_1 = {"batch_key": (1, 2), "key": 1}
    fake_entity_2 = {"batch_key": (1, 2), "key": 2}
    fake_entity_3 = {"batch_key": (1, 2), "key": 3}
    fake_entity_4 = {"batch_key": (1, 2), "key": 4}

    delete_entity_1 = {"batch_key": (1, 2), "key": 5}
    delete_entity_2 = {"batch_key": (1, 2), "key": 6}
    delete_entity_3 = {"batch_key": (1, 2), "key": 7}

    mock_get_batch_key.side_effect = lambda r, m: m["batch_key"]

    ts = datetime(2024, 1, 2, 3, 4, 6)
    b = AggregatorBatchedEntities(
        ts,
        resource,
        [fake_entity_1, fake_entity_2, fake_entity_3, fake_entity_4],
        [delete_entity_1, delete_entity_2, delete_entity_3],
    )

    assert b.timestamp == ts
    assert_batched_entities(b, type(fake_entity_1), type(delete_entity_1), 4, 3)
    assert len(b.models_by_batch_key) == 1, "Expecting a single unique key"
    assert b.models_by_batch_key[(1, 2)] == [fake_entity_1, fake_entity_2, fake_entity_3, fake_entity_4]

    assert len(b.deleted_by_batch_key) == 1, "Expecting a single unique key"
    assert b.deleted_by_batch_key[(1, 2)] == [delete_entity_1, delete_entity_2, delete_entity_3]

    assert mock_get_batch_key.call_count == 7, "One for every entity"
    assert all([call_args.args[0] == resource for call_args in mock_get_batch_key.call_args_list])


@mock.patch("envoy.notification.crud.batch.get_batch_key")
@pytest.mark.parametrize("resource", [(r) for r in SubscriptionResource])
def test_AggregatorBatchedEntities_multi_batch(mock_get_batch_key: mock.MagicMock, resource: SubscriptionResource):
    """This completely isolates the batching algorithm from the use of get_batch_key / the underlying models"""

    fake_entity_1 = {"batch_key": (1, 2), "key": 1}  # batch 1
    fake_entity_2 = {"batch_key": (1, 3), "key": 2}  # batch 2
    fake_entity_3 = {"batch_key": (1, 2), "key": 3}  # batch 1
    fake_entity_4 = {"batch_key": (2, 1), "key": 4}  # batch 3

    delete_entity_1 = {"batch_key": (1, 2), "key": 5}  # batch 1
    delete_entity_2 = {"batch_key": (1, 3), "key": 6}  # batch 2
    delete_entity_3 = {"batch_key": (1, 2), "key": 7}  # batch 1

    mock_get_batch_key.side_effect = lambda r, m: m["batch_key"]

    ts = datetime(2024, 2, 2, 3, 4, 7)
    b = AggregatorBatchedEntities(
        ts,
        resource,
        [fake_entity_1, fake_entity_2, fake_entity_3, fake_entity_4],
        [delete_entity_1, delete_entity_2, delete_entity_3],
    )

    assert b.timestamp == ts
    assert_batched_entities(b, type(fake_entity_1), type(delete_entity_1), 4, 3)
    assert len(b.models_by_batch_key) == 3
    assert b.models_by_batch_key[(1, 2)] == [fake_entity_1, fake_entity_3]
    assert b.models_by_batch_key[(1, 3)] == [fake_entity_2]
    assert b.models_by_batch_key[(2, 1)] == [fake_entity_4]

    assert len(b.deleted_by_batch_key) == 2
    assert b.deleted_by_batch_key[(1, 2)] == [delete_entity_1, delete_entity_3]
    assert b.deleted_by_batch_key[(1, 3)] == [delete_entity_2]

    assert mock_get_batch_key.call_count == 7, "One for every entity"
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
                site_reading_type=SiteReadingType(aggregator_id=1, site_id=2, site_reading_type_id=3, group_id=4),
                site_reading_type_id=3,
            ),
            (1, 2, 4),
        ),
        (
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
            DynamicOperatingEnvelope(
                dynamic_operating_envelope_id=99,
                site_id=2,
                site_control_group_id=3,
                site=Site(site_id=2, aggregator_id=1),
            ),
            (1, 2, 3),
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
        (
            SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
            SiteScopedRuntimeServerConfig(
                aggregator_id=11,
                site_id=22,
                original=generate_class_instance(RuntimeServerConfig),
            ),
            (11, 22),
        ),
        (
            SubscriptionResource.DEFAULT_SITE_CONTROL,
            ControlGroupScopedDefaultSiteControl(
                site_control_group_id=33,
                original=DefaultSiteControl(site_id=11, site=Site(site_id=11, aggregator_id=22)),
            ),
            (22, 11, 33),
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
                site_reading_type=SiteReadingType(site_reading_type_id=3, group_id=4),
            ),
            4,
        ),
        (
            SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
            DynamicOperatingEnvelope(
                dynamic_operating_envelope_id=99,
                site_id=2,
                site_control_group_id=3,
            ),
            3,
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
        (
            SubscriptionResource.DEFAULT_SITE_CONTROL,
            ControlGroupScopedDefaultSiteControl(
                site_control_group_id=4, original=generate_class_instance(DefaultSiteControl, seed=101)
            ),
            4,
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
        (
            SubscriptionResource.DEFAULT_SITE_CONTROL,
            ControlGroupScopedDefaultSiteControl(
                site_control_group_id=4, original=generate_class_instance(DefaultSiteControl, seed=101, site_id=5)
            ),
            5,
        ),
        (
            SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
            SiteScopedRuntimeServerConfig(
                aggregator_id=1, site_id=2, original=generate_class_instance(RuntimeServerConfig, seed=101)
            ),
            2,
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
async def test_fetch_sites_by_timestamp_no_archive(pg_base_config, timestamp: datetime, expected_sites: list[Site]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_sites_by_changed_at(session, timestamp)
        assert_batched_entities(batch, Site, ArchiveSite, len(expected_sites), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda e: e.site_id)


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
        assert_batched_entities(batch, Site, ArchiveSite, len(all_entities), 0)
        assert len(batch.deleted_by_batch_key) == 0
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda e: e.site_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4, 5, 6]) == set([e.site_id for e in list_entities])
        assert set([NULL_AGGREGATOR_ID, 1, 2]) == set(
            [e.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, Site, ArchiveSite, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


@pytest.mark.anyio
async def test_fetch_sites_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on site 1
    timestamp = datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc)
    expected_active_site_ids = [1]
    expected_active_nmis = ["1111111111"]
    expected_deleted_site_ids = [70, 72]
    assert len(expected_active_site_ids) == len(expected_active_nmis), "Keep these in sync"

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # One of these will be picked up
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(generate_class_instance(ArchiveSite, seed=22, aggregator_id=1, site_id=70, deleted_time=timestamp))
        session.add(
            generate_class_instance(
                ArchiveSite, seed=33, aggregator_id=1, site_id=70, deleted_time=timestamp + timedelta(seconds=5)
            )
        )

        # No deleted time so ignored
        session.add(generate_class_instance(ArchiveSite, seed=44, aggregator_id=1, site_id=71))

        # This will be picked up
        session.add(generate_class_instance(ArchiveSite, seed=66, aggregator_id=2, site_id=72, deleted_time=timestamp))
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_sites_by_changed_at(session, timestamp)
        assert_batched_entities(batch, Site, ArchiveSite, len(expected_active_site_ids), len(expected_deleted_site_ids))
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.site_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.site_id)

        assert set(expected_active_site_ids) == set([e.site_id for e in active_list_entities])
        assert set(expected_active_nmis) == set([e.nmi for e in active_list_entities])
        assert set(expected_deleted_site_ids) == set([e.site_id for e in deleted_list_entities])

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, Site, ArchiveSite, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


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
        assert_batched_entities(batch, TariffGeneratedRate, ArchiveTariffGeneratedRate, len(expected_rates), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda rate: rate.tariff_generated_rate_id)

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
        assert_batched_entities(batch, TariffGeneratedRate, ArchiveTariffGeneratedRate, len(all_entities), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda rate: rate.tariff_generated_rate_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4]) == set([e.tariff_generated_rate_id for e in list_entities])
        assert set([1, 2]) == set(
            [e.site.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_rates_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, TariffGeneratedRate, ArchiveTariffGeneratedRate, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


@pytest.mark.anyio
async def test_fetch_rates_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on tariff_generated_rate 1
    timestamp = datetime(2022, 3, 4, 11, 22, 33, 500000, tzinfo=timezone.utc)
    expected_active_rate_ids = [1]
    expected_deleted_rate_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a parent "archive" site that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=22,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=33,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
                nmi="deleted70",
                timezone_id="Australia/Brisbane",
            )
        )

        # This deleted site will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=44,
                aggregator_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject archive rates (only most recent is used)
        session.add(
            generate_class_instance(ArchiveTariffGeneratedRate, seed=55, site_id=1, tariff_generated_rate_id=21)
        )
        session.add(
            generate_class_instance(
                ArchiveTariffGeneratedRate,
                seed=66,
                site_id=1,
                tariff_generated_rate_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveTariffGeneratedRate,
                seed=77,
                site_id=70,
                tariff_generated_rate_id=21,
                tariff_id=91,
                start_time=datetime(2011, 11, 1, 12, 0, 0, tzinfo=timezone.utc),
                deleted_time=timestamp,
                duration_seconds=21,  # for identifying this record later
            )
        )

        # No deleted time so ignored
        session.add(
            generate_class_instance(ArchiveTariffGeneratedRate, seed=88, site_id=1, tariff_generated_rate_id=22)
        )

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveTariffGeneratedRate,
                seed=99,
                site_id=1,
                tariff_generated_rate_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveTariffGeneratedRate,
                seed=1010,
                site_id=2,
                tariff_generated_rate_id=24,
                tariff_id=92,
                start_time=datetime(2011, 11, 2, 12, 0, 0, tzinfo=timezone.utc),
                deleted_time=timestamp,
                duration_seconds=24,  # for identifying this record later
            )
        )
        session.add(
            generate_class_instance(
                ArchiveTariffGeneratedRate,
                seed=1111,
                site_id=3,
                tariff_generated_rate_id=25,
                tariff_id=93,
                start_time=datetime(2011, 11, 3, 12, 0, 0, tzinfo=timezone.utc),
                deleted_time=timestamp,
                duration_seconds=25,  # for identifying this record later
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_rates_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            TariffGeneratedRate,
            ArchiveTariffGeneratedRate,
            len(expected_active_rate_ids),
            len(expected_deleted_rate_ids),
        )
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.tariff_generated_rate_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.tariff_generated_rate_id)

        assert set(expected_active_rate_ids) == set([e.tariff_generated_rate_id for e in active_list_entities])
        assert set(expected_deleted_rate_ids) == set([e.tariff_generated_rate_id for e in deleted_list_entities])

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all([isinstance(e.site, Site) for v_list in batch.models_by_batch_key.values() for e in v_list])
        assert all(
            [
                hasattr(e, "site") and (isinstance(e.site, Site) or isinstance(e.site, ArchiveSite))
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [
                e.duration_seconds == e.tariff_generated_rate_id
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, TariffGeneratedRate, ArchiveTariffGeneratedRate, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


@pytest.mark.parametrize(
    "timestamp,expected_does",
    [
        (
            datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc),
            [
                DynamicOperatingEnvelope(
                    dynamic_operating_envelope_id=1,
                    site_control_group_id=1,
                    site_id=1,
                    calculation_log_id=2,
                    created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    changed_time=datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc),
                    start_time=datetime(2022, 5, 7, 1, 2, 0, 0, tzinfo=timezone(timedelta(hours=10))),
                    duration_seconds=11,
                    randomize_start_seconds=111,
                    import_limit_active_watts=Decimal("1.11"),
                    export_limit_watts=Decimal("-1.22"),
                    generation_limit_active_watts=Decimal("1.33"),
                    load_limit_active_watts=Decimal("-1.44"),
                    set_point_percentage=Decimal("1.55"),
                    ramp_time_seconds=Decimal("1.66"),
                    end_time=datetime(2022, 5, 7, 1, 2, 11, 0, tzinfo=timezone(timedelta(hours=10))),  # Generated Col
                    superseded=False,
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
        assert_batched_entities(batch, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, len(expected_does), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.dynamic_operating_envelope_id)

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
        assert_batched_entities(batch, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, len(all_entities), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda rate: rate.dynamic_operating_envelope_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4]) == set([e.dynamic_operating_envelope_id for e in list_entities])
        assert set([1, 2]) == set(
            [e.site.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_does_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


@pytest.mark.anyio
async def test_fetch_does_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on doe 1
    timestamp = datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc)
    expected_active_doe_ids = [1]
    expected_deleted_doe_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a parent "archive" site that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=22,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=33,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
                nmi="deleted70",
                timezone_id="Australia/Brisbane",
            )
        )

        # This deleted site will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=44,
                aggregator_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject archive rates (only most recent is used)
        session.add(
            generate_class_instance(
                ArchiveDynamicOperatingEnvelope,
                seed=55,
                site_id=1,
                dynamic_operating_envelope_id=21,
            )
        )
        session.add(
            generate_class_instance(
                ArchiveDynamicOperatingEnvelope,
                seed=66,
                site_id=1,
                dynamic_operating_envelope_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveDynamicOperatingEnvelope,
                seed=77,
                site_id=70,
                dynamic_operating_envelope_id=21,
                deleted_time=timestamp,
                duration_seconds=21,  # for identifying this record later
            )
        )

        # No deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveDynamicOperatingEnvelope, seed=88, site_id=1, dynamic_operating_envelope_id=22
            )
        )

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveDynamicOperatingEnvelope,
                seed=99,
                site_id=1,
                dynamic_operating_envelope_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveDynamicOperatingEnvelope,
                seed=1010,
                site_id=2,
                dynamic_operating_envelope_id=24,
                deleted_time=timestamp,
                duration_seconds=24,  # for identifying this record later
            )
        )
        session.add(
            generate_class_instance(
                ArchiveDynamicOperatingEnvelope,
                seed=1111,
                site_id=3,
                dynamic_operating_envelope_id=25,
                deleted_time=timestamp,
                duration_seconds=25,  # for identifying this record later
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_does_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            DynamicOperatingEnvelope,
            ArchiveDynamicOperatingEnvelope,
            len(expected_active_doe_ids),
            len(expected_deleted_doe_ids),
        )
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.dynamic_operating_envelope_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.dynamic_operating_envelope_id)

        assert set(expected_active_doe_ids) == set([e.dynamic_operating_envelope_id for e in active_list_entities])
        assert set(expected_deleted_doe_ids) == set([e.dynamic_operating_envelope_id for e in deleted_list_entities])

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all([isinstance(e.site, Site) for v_list in batch.models_by_batch_key.values() for e in v_list])
        assert all(
            [
                hasattr(e, "site") and (isinstance(e.site, Site) or isinstance(e.site, ArchiveSite))
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [
                e.duration_seconds == e.dynamic_operating_envelope_id
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


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
        assert_batched_entities(batch, SiteReading, ArchiveSiteReading, len(expected_readings), 0)
        assert len(batch.deleted_by_batch_key) == 0
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
        assert_batched_entities(batch, SiteReading, ArchiveSiteReading, len(all_entities), 0)
        assert len(batch.deleted_by_batch_key) == 0
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda reading: reading.site_reading_id)

        assert len(list_entities) == len(all_entities)
        assert set([1, 2, 3, 4]) == set([e.site_reading_id for e in list_entities])
        assert set([1, 3]) == set(
            [e.site_reading_type.aggregator_id for e in list_entities]
        ), "All aggregator IDs should be represented"

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_readings_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, SiteReading, ArchiveSiteReading, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


@pytest.mark.anyio
async def test_fetch_readings_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on reading 1
    timestamp = datetime(2022, 6, 7, 11, 22, 33, 500000, tzinfo=timezone.utc)
    expected_active_reading_ids = [1]
    expected_deleted_reading_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a parent "archive" site reading type that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSiteReadingType, seed=11, aggregator_id=1, site_reading_type_id=70))
        session.add(
            generate_class_instance(
                ArchiveSiteReadingType,
                seed=22,
                aggregator_id=1,
                site_reading_type_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteReadingType,
                seed=33,
                aggregator_id=1,
                site_reading_type_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site reading type will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSiteReadingType,
                seed=44,
                aggregator_id=1,
                site_reading_type_id=1,
            )
        )

        # Inject archive readings (only most recent is used)
        session.add(generate_class_instance(ArchiveSiteReading, seed=55, site_reading_type_id=1, site_reading_id=21))
        session.add(
            generate_class_instance(
                ArchiveSiteReading,
                seed=66,
                site_reading_type_id=1,
                site_reading_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteReading,
                seed=77,
                site_reading_type_id=70,
                site_reading_id=21,
                deleted_time=timestamp,
                value=21,  # for identifying this record later
            )
        )

        # No deleted time so ignored
        session.add(generate_class_instance(ArchiveSiteReading, seed=88, site_reading_type_id=1, site_reading_id=22))

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveSiteReading,
                seed=99,
                site_reading_type_id=1,
                site_reading_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveSiteReading,
                seed=1010,
                site_reading_type_id=2,
                site_reading_id=24,
                deleted_time=timestamp,
                value=24,  # for identifying this record later
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteReading,
                seed=1111,
                site_reading_type_id=3,
                site_reading_id=25,
                deleted_time=timestamp,
                value=25,  # for identifying this record later
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_readings_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            SiteReading,
            ArchiveSiteReading,
            len(expected_active_reading_ids),
            len(expected_deleted_reading_ids),
        )
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.site_reading_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.site_reading_id)

        assert set(expected_active_reading_ids) == set([e.site_reading_id for e in active_list_entities])
        assert set(expected_deleted_reading_ids) == set([e.site_reading_id for e in deleted_list_entities])

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all(
            [
                isinstance(e.site_reading_type, SiteReadingType)
                for v_list in batch.models_by_batch_key.values()
                for e in v_list
            ]
        )
        assert all(
            [
                hasattr(e, "site_reading_type")
                and (
                    isinstance(e.site_reading_type, SiteReadingType)
                    or isinstance(e.site_reading_type, ArchiveSiteReadingType)
                )
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all([e.value == e.site_reading_id for v_list in batch.deleted_by_batch_key.values() for e in v_list])

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, SiteReading, ArchiveSiteReading, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


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
        assert_batched_entities(batch, SiteDERAvailability, ArchiveSiteDERAvailability, len(expected_ids), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_availability_id)

        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_availability_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.anyio
async def test_fetch_der_availability_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on der availability 1
    timestamp = datetime(2022, 7, 23, 10, 3, 23, 500000, tzinfo=timezone.utc)
    expected_active_avail_ids = [1]
    expected_deleted_avail_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a grandparent "archive" site that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=22,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=33,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=44,
                aggregator_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject a parent "archive" site_der that were deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSiteDER, seed=11, site_der_id=80, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=55,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=66,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site_der will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=77,
                site_der_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject archive der availability (only most recent is used)
        session.add(
            generate_class_instance(ArchiveSiteDERAvailability, seed=88, site_der_id=1, site_der_availability_id=21)
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERAvailability,
                seed=99,
                site_der_id=1,
                site_der_availability_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERAvailability,
                seed=1010,
                site_der_id=1,
                site_der_availability_id=21,
                max_charge_duration_sec=21,  # for identifying this record later
                deleted_time=timestamp,
            )
        )

        # No deleted time so ignored
        session.add(
            generate_class_instance(ArchiveSiteDERAvailability, seed=1111, site_der_id=1, site_der_availability_id=22)
        )

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveSiteDERAvailability,
                seed=1212,
                site_der_id=1,
                site_der_availability_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveSiteDERAvailability,
                seed=1313,
                site_der_id=2,
                site_der_availability_id=24,
                max_charge_duration_sec=24,  # for identifying this record later
                deleted_time=timestamp,
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERAvailability,
                seed=1414,
                site_der_id=80,
                site_der_availability_id=25,
                max_charge_duration_sec=25,  # for identifying this record later
                deleted_time=timestamp,
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_availability_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            SiteDERAvailability,
            ArchiveSiteDERAvailability,
            len(expected_active_avail_ids),
            len(expected_deleted_avail_ids),
        )
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.site_der_availability_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.site_der_availability_id)

        assert set(expected_active_avail_ids) == set([e.site_der_availability_id for e in active_list_entities])
        assert set(expected_deleted_avail_ids) == set([e.site_der_availability_id for e in deleted_list_entities])

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all(
            [
                isinstance(e.site_der, SiteDER) and isinstance(e.site_der.site, Site)
                for v_list in batch.models_by_batch_key.values()
                for e in v_list
            ]
        )
        assert all(
            [
                hasattr(e, "site_der")
                and (isinstance(e.site_der, SiteDER) or isinstance(e.site_der, ArchiveSiteDER))
                and (isinstance(e.site_der.site, Site) or isinstance(e.site_der.site, ArchiveSite))
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [
                e.max_charge_duration_sec == e.site_der_availability_id
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_der_availability_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, SiteDERAvailability, ArchiveSiteDERAvailability, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


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
        assert_batched_entities(batch, SiteDERRating, ArchiveSiteDERRating, len(expected_ids), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_rating_id)

        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_rating_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.anyio
async def test_fetch_der_rating_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on der rating 1
    timestamp = datetime(2022, 4, 13, 10, 1, 42, 500000, tzinfo=timezone.utc)
    expected_active_rating_ids = [1]
    expected_deleted_rating_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a grandparent "archive" site that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=22,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=33,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=44,
                aggregator_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject a parent "archive" site_der that were deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSiteDER, seed=11, site_der_id=80, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=55,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=66,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site_der will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=77,
                site_der_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject archive der rating (only most recent is used)
        session.add(generate_class_instance(ArchiveSiteDERRating, seed=88, site_der_id=1, site_der_rating_id=21))
        session.add(
            generate_class_instance(
                ArchiveSiteDERRating,
                seed=99,
                site_der_id=1,
                site_der_rating_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERRating,
                seed=1010,
                site_der_id=1,
                site_der_rating_id=21,
                max_w_value=21,  # For identifying this record later
                deleted_time=timestamp,
            )
        )

        # No deleted time so ignored
        session.add(generate_class_instance(ArchiveSiteDERRating, seed=1111, site_der_id=1, site_der_rating_id=22))

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveSiteDERRating,
                seed=1212,
                site_der_id=1,
                site_der_rating_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveSiteDERRating,
                seed=1313,
                site_der_id=2,
                site_der_rating_id=24,
                max_w_value=24,  # For identifying this record later
                deleted_time=timestamp,
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERRating,
                seed=1414,
                site_der_id=80,
                site_der_rating_id=25,
                max_w_value=25,  # For identifying this record later
                deleted_time=timestamp,
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_rating_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            SiteDERRating,
            ArchiveSiteDERRating,
            len(expected_active_rating_ids),
            len(expected_deleted_rating_ids),
        )
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.site_der_rating_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.site_der_rating_id)

        assert set(expected_active_rating_ids) == set([e.site_der_rating_id for e in active_list_entities])
        assert set(expected_deleted_rating_ids) == set([e.site_der_rating_id for e in deleted_list_entities])

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all(
            [
                isinstance(e.site_der, SiteDER) and isinstance(e.site_der.site, Site)
                for v_list in batch.models_by_batch_key.values()
                for e in v_list
            ]
        )
        assert all(
            [
                hasattr(e, "site_der")
                and (isinstance(e.site_der, SiteDER) or isinstance(e.site_der, ArchiveSiteDER))
                and (isinstance(e.site_der.site, Site) or isinstance(e.site_der.site, ArchiveSite))
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [e.max_w_value == e.site_der_rating_id for v_list in batch.deleted_by_batch_key.values() for e in v_list]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_der_availability_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, SiteDERRating, ArchiveSiteDERRating, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


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
        assert_batched_entities(batch, SiteDERSetting, ArchiveSiteDERSetting, len(expected_ids), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_setting_id)

        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_setting_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.anyio
async def test_fetch_der_setting_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on der setting 1
    timestamp = datetime(2022, 2, 9, 11, 6, 44, 500000, tzinfo=timezone.utc)
    expected_active_setting_ids = [1]
    expected_deleted_setting_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a grandparent "archive" site that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=22,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=33,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=44,
                aggregator_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject a parent "archive" site_der that were deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSiteDER, seed=11, site_der_id=80, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=55,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=66,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site_der will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=77,
                site_der_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject archive der rating (only most recent is used)
        session.add(generate_class_instance(ArchiveSiteDERSetting, seed=88, site_der_id=1, site_der_setting_id=21))
        session.add(
            generate_class_instance(
                ArchiveSiteDERSetting,
                seed=99,
                site_der_id=1,
                site_der_setting_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERSetting,
                seed=1010,
                site_der_id=1,
                site_der_setting_id=21,
                max_w_value=21,  # For identifying this record later
                deleted_time=timestamp,
            )
        )

        # No deleted time so ignored
        session.add(generate_class_instance(ArchiveSiteDERSetting, seed=1111, site_der_id=1, site_der_setting_id=22))

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveSiteDERSetting,
                seed=1212,
                site_der_id=1,
                site_der_setting_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveSiteDERSetting,
                seed=1313,
                site_der_id=2,
                site_der_setting_id=24,
                max_w_value=24,  # For identifying this record later
                deleted_time=timestamp,
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERSetting,
                seed=1414,
                site_der_id=80,
                site_der_setting_id=25,
                max_w_value=25,  # For identifying this record later
                deleted_time=timestamp,
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_setting_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            SiteDERSetting,
            ArchiveSiteDERSetting,
            len(expected_active_setting_ids),
            len(expected_deleted_setting_ids),
        )
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.site_der_setting_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.site_der_setting_id)

        assert set(expected_active_setting_ids) == set([e.site_der_setting_id for e in active_list_entities])
        assert set(expected_deleted_setting_ids) == set([e.site_der_setting_id for e in deleted_list_entities])

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all(
            [
                isinstance(e.site_der, SiteDER) and isinstance(e.site_der.site, Site)
                for v_list in batch.models_by_batch_key.values()
                for e in v_list
            ]
        )
        assert all(
            [
                hasattr(e, "site_der")
                and (isinstance(e.site_der, SiteDER) or isinstance(e.site_der, ArchiveSiteDER))
                and (isinstance(e.site_der.site, Site) or isinstance(e.site_der.site, ArchiveSite))
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [e.max_w_value == e.site_der_setting_id for v_list in batch.deleted_by_batch_key.values() for e in v_list]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_der_availability_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, SiteDERSetting, ArchiveSiteDERSetting, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


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
        assert_batched_entities(batch, SiteDERStatus, ArchiveSiteDERStatus, len(expected_ids), 0)
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda doe: doe.site_der_status_id)

        assert all([isinstance(e, SiteDERStatus) for e in list_entities])
        for i in range(len(expected_ids)):
            assert list_entities[i].site_der_status_id == expected_ids[i]

        assert all([isinstance(e.site_der, SiteDER) for e in list_entities]), "SiteDER relationship populated"
        assert all([isinstance(e.site_der.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.anyio
async def test_fetch_der_status_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on der status 1
    timestamp = datetime(2022, 11, 1, 11, 5, 4, 500000, tzinfo=timezone.utc)
    expected_active_status_ids = [1]
    expected_deleted_status_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a grandparent "archive" site that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=22,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=33,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=44,
                aggregator_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject a parent "archive" site_der that were deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSiteDER, seed=11, site_der_id=80, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=55,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=66,
                site_der_id=80,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
            )
        )

        # This deleted site_der will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=77,
                site_der_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject archive der rating (only most recent is used)
        session.add(
            generate_class_instance(
                ArchiveSiteDERStatus, seed=88, site_der_id=1, site_der_status_id=21, manufacturer_status="n/a"
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERStatus,
                seed=99,
                site_der_id=1,
                site_der_status_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
                manufacturer_status="n/a",
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERStatus,
                seed=1010,
                site_der_id=1,
                site_der_status_id=21,
                deleted_time=timestamp,
                manufacturer_status="ms21",  # For identifying this record later
            )
        )

        # No deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveSiteDERStatus, seed=1111, site_der_id=1, site_der_status_id=22, manufacturer_status="n/a"
            )
        )

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveSiteDERStatus,
                seed=1212,
                site_der_id=1,
                site_der_status_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
                manufacturer_status="n/a",
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveSiteDERStatus,
                seed=1313,
                site_der_id=2,
                site_der_status_id=24,
                deleted_time=timestamp,
                manufacturer_status="ms24",  # For identifying this record later
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDERStatus,
                seed=1414,
                site_der_id=80,
                site_der_status_id=25,
                deleted_time=timestamp,
                manufacturer_status="ms25",  # For identifying this record later
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_der_status_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            SiteDERStatus,
            ArchiveSiteDERStatus,
            len(expected_active_status_ids),
            len(expected_deleted_status_ids),
        )
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.site_der_status_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.site_der_status_id)

        assert set(expected_active_status_ids) == set([e.site_der_status_id for e in active_list_entities])
        assert set(expected_deleted_status_ids) == set([e.site_der_status_id for e in deleted_list_entities])

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all(
            [
                isinstance(e.site_der, SiteDER) and isinstance(e.site_der.site, Site)
                for v_list in batch.models_by_batch_key.values()
                for e in v_list
            ]
        )
        assert all(
            [
                hasattr(e, "site_der")
                and (isinstance(e.site_der, SiteDER) or isinstance(e.site_der, ArchiveSiteDER))
                and (isinstance(e.site_der.site, Site) or isinstance(e.site_der.site, ArchiveSite))
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [
                e.manufacturer_status == f"ms{e.site_der_status_id}"
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_der_availability_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(empty_batch, SiteDERStatus, ArchiveSiteDERStatus, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


@pytest.mark.parametrize(
    "timestamp,expected_ids",
    [
        (
            datetime(2023, 5, 1, 2, 2, 2, 500000, tzinfo=timezone.utc),
            [1, 2],
        ),
        (
            datetime(2022, 2, 3, 4, 5, 8),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_default_site_controls_by_changed_at(pg_base_config, timestamp: datetime, expected_ids: list[int]):
    """Tests that entities are filtered/returned correctly"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_default_site_controls_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            ControlGroupScopedDefaultSiteControl,
            ArchiveControlGroupScopedDefaultSiteControl,
            len(expected_ids),
            0,
        )
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        list_entities.sort(key=lambda default: default.original.default_site_control_id)

        assert all([isinstance(e, ControlGroupScopedDefaultSiteControl) for e in list_entities])
        assert all([e.site_control_group_id == 1 for e in list_entities]), "The only SiteControlGroup ID in the DB"
        for i in range(len(expected_ids)):
            assert list_entities[i].original.default_site_control_id == expected_ids[i]

        assert all([isinstance(e.original.site, Site) for e in list_entities]), "Site relationship populated"


@pytest.mark.anyio
async def test_fetch_default_site_controls_by_changed_at_multiple_groups(pg_base_config):
    """Tests that multiple SiteControlGroup's generate copies of the defaults per SiteControlGroup ID"""
    timestamp = datetime(2023, 5, 1, 2, 2, 2, 500000, tzinfo=timezone.utc)
    expected_default_group_ids = [(1, 1), (1, 99), (2, 1), (2, 99)]

    async with generate_async_session(pg_base_config) as session:
        session.add(generate_class_instance(SiteControlGroup, site_control_group_id=99))
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_default_site_controls_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            ControlGroupScopedDefaultSiteControl,
            ArchiveControlGroupScopedDefaultSiteControl,
            len(expected_default_group_ids),
            0,
        )
        assert expected_default_group_ids == [
            (e.original.default_site_control_id, e.site_control_group_id)
            for _, entities in batch.models_by_batch_key.items()
            for e in entities
        ]


@pytest.mark.anyio
async def test_fetch_default_site_controls_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on default 1 and 2
    timestamp = datetime(2023, 5, 1, 2, 2, 2, 500000, tzinfo=timezone.utc)
    expected_active_default_ids = [1, 2]
    expected_deleted_default_ids = [21, 24, 25]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject a parent "archive" site that was deleted - the "newest" deleted value will be used
        session.add(generate_class_instance(ArchiveSite, seed=11, aggregator_id=1, site_id=70))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=22,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=10),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=33,
                aggregator_id=1,
                site_id=70,
                deleted_time=timestamp - timedelta(seconds=5),  # Doesn't need to match the timestamp
                nmi="deleted70",
                timezone_id="Australia/Brisbane",
            )
        )

        # This deleted site will be ignored in favour of the version in the active table
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=44,
                aggregator_id=1,
                site_id=1,
                deleted_time=timestamp,
            )
        )

        # Inject archive defaults (only most recent is used)
        session.add(
            generate_class_instance(
                ArchiveDefaultSiteControl,
                seed=55,
                site_id=1,
                default_site_control_id=21,
            )
        )
        session.add(
            generate_class_instance(
                ArchiveDefaultSiteControl,
                seed=66,
                site_id=1,
                default_site_control_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveDefaultSiteControl,
                seed=77,
                site_id=70,
                default_site_control_id=21,
                deleted_time=timestamp,
                ramp_rate_percent_per_second=21,  # for identifying this record later
            )
        )

        # No deleted time so ignored
        session.add(generate_class_instance(ArchiveDefaultSiteControl, seed=88, site_id=1, default_site_control_id=22))

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveDefaultSiteControl,
                seed=99,
                site_id=1,
                default_site_control_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveDefaultSiteControl,
                seed=1010,
                site_id=2,
                default_site_control_id=24,
                deleted_time=timestamp,
                ramp_rate_percent_per_second=24,  # for identifying this record later
            )
        )
        session.add(
            generate_class_instance(
                ArchiveDefaultSiteControl,
                seed=1111,
                site_id=3,
                default_site_control_id=25,
                deleted_time=timestamp,
                ramp_rate_percent_per_second=25,  # for identifying this record later
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_default_site_controls_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            ControlGroupScopedDefaultSiteControl,
            ArchiveControlGroupScopedDefaultSiteControl,
            len(expected_active_default_ids),
            len(expected_deleted_default_ids),
        )

        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        active_list_entities.sort(key=lambda e: e.original.default_site_control_id)

        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        deleted_list_entities.sort(key=lambda e: e.original.default_site_control_id)

        assert set(expected_active_default_ids) == set(
            [e.original.default_site_control_id for e in active_list_entities]
        )
        assert set(expected_deleted_default_ids) == set(
            [e.original.default_site_control_id for e in deleted_list_entities]
        )

        # Ensure the parent ORM relationship is populated for deleted/active instances
        assert all([isinstance(e.original.site, Site) for v_list in batch.models_by_batch_key.values() for e in v_list])
        assert all(
            [
                hasattr(e.original, "site")
                and (isinstance(e.original.site, Site) or isinstance(e.original.site, ArchiveSite))
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [
                e.original.ramp_rate_percent_per_second == e.original.default_site_control_id
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(
            empty_batch, ControlGroupScopedDefaultSiteControl, ArchiveControlGroupScopedDefaultSiteControl, 0, 0
        )
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0


@pytest.mark.anyio
async def test_fetch_runtime_config_by_changed_at(pg_base_config):
    """Tests that runtime config can be fetched and that it references all aggregator/site combos"""
    async with generate_async_session(pg_base_config) as session:
        empty_batch = await fetch_runtime_config_by_changed_at(
            session, datetime(2000, 1, 1, 1, 1, 1, tzinfo=timezone.utc)
        )
        assert_batched_entities(empty_batch, SiteScopedRuntimeServerConfig, ArchiveSiteScopedRuntimeServerConfig, 0, 0)
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0

    # One for every site in the DB
    expected_agg_site_cfg_id = [
        (1, 1, 1),
        (1, 2, 1),
        (2, 3, 1),
        (1, 4, 1),
        (0, 5, 1),
        (0, 6, 1),
    ]
    async with generate_async_session(pg_base_config) as session:
        batch = await fetch_runtime_config_by_changed_at(
            session, datetime(2023, 5, 1, 1, 1, 1, 500000, tzinfo=timezone.utc)
        )
        assert_batched_entities(
            batch,
            SiteScopedRuntimeServerConfig,
            ArchiveSiteScopedRuntimeServerConfig,
            len(expected_agg_site_cfg_id),
            0,
        )
        all_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        assert all([isinstance(e.original, RuntimeServerConfig) for e in all_entities])
        assert [(e.aggregator_id, e.site_id, e.original.runtime_server_config_id) for e in all_entities]


@pytest.mark.parametrize(
    "timestamp, expected_agg_site_group_ids",
    [
        (
            datetime(2021, 4, 5, 10, 1, 0, 500000, tzinfo=timezone.utc),
            [(1, 1, 1), (1, 2, 1), (2, 3, 1), (1, 4, 1), (0, 5, 1), (0, 6, 1)],
        ),
        (
            datetime(2022, 2, 3, 4, 5, 8),  # timestamp mismatch
            [],
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_site_control_groups_by_changed_at(
    pg_base_config, timestamp: datetime, expected_agg_site_group_ids: list[tuple[int, int, int]]
):
    """Tests that entities are filtered/returned correctly and expand per site.

    expected_agg_site_group_ids: tuple of aggregator_id, site_id, site_control_group_id"""
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_site_control_groups_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            SiteScopedSiteControlGroup,
            ArchiveSiteScopedSiteControlGroup,
            len(expected_agg_site_group_ids),
            0,
        )
        list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]

        assert all([isinstance(e, SiteScopedSiteControlGroup) for e in list_entities])
        actual_agg_site_group_ids = [
            (e.aggregator_id, e.site_id, e.original.site_control_group_id) for e in list_entities
        ]

        assert expected_agg_site_group_ids == actual_agg_site_group_ids


@pytest.mark.anyio
async def test_fetch_site_control_groups_by_timestamp_with_archive(pg_base_config):
    """Tests that entities are filtered/returned correctly and include archive data"""

    # This matches the changed_time on site_control_group 1
    timestamp = datetime(2021, 4, 5, 10, 1, 0, 500000, tzinfo=timezone.utc)
    expected_active_default_ids = [1]
    expected_deleted_default_ids = [21, 24, 25]
    expected_site_agg_ids = [(1, 1), (1, 2), (2, 3), (1, 4), (0, 5), (0, 6)]

    # inject a bunch of archival data
    async with generate_async_session(pg_base_config) as session:

        # Inject archive defaults (only most recent is used)
        session.add(
            generate_class_instance(
                ArchiveSiteControlGroup,
                seed=55,
                site_control_group_id=21,
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteControlGroup,
                seed=66,
                site_control_group_id=21,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteControlGroup,
                seed=77,
                site_control_group_id=21,
                deleted_time=timestamp,
                primacy=21,  # for identifying this record later
            )
        )

        # No deleted time so ignored
        session.add(generate_class_instance(ArchiveSiteControlGroup, seed=88, site_control_group_id=22))

        # Wrong deleted time so ignored
        session.add(
            generate_class_instance(
                ArchiveSiteControlGroup,
                seed=99,
                site_control_group_id=23,
                deleted_time=timestamp - timedelta(seconds=5),
            )
        )

        # These will be picked up
        session.add(
            generate_class_instance(
                ArchiveSiteControlGroup,
                seed=1010,
                site_control_group_id=24,
                deleted_time=timestamp,
                primacy=24,  # for identifying this record later
            )
        )
        session.add(
            generate_class_instance(
                ArchiveSiteControlGroup,
                seed=1111,
                site_control_group_id=25,
                deleted_time=timestamp,
                primacy=25,  # for identifying this record later
            )
        )
        await session.commit()

    # Now see if the fetch grabs everything
    async with generate_async_session(pg_base_config) as session:
        # Need to unroll the batching into a single list (batching is tested elsewhere)
        batch = await fetch_site_control_groups_by_changed_at(session, timestamp)
        assert_batched_entities(
            batch,
            SiteScopedSiteControlGroup,
            ArchiveSiteScopedSiteControlGroup,
            len(expected_active_default_ids) * len(expected_site_agg_ids),
            len(expected_deleted_default_ids) * len(expected_site_agg_ids),
        )

        # The resulting entities will be multiplied out by the expected_site_agg_ids entries
        # We will check that every expected SiteControlGroup is found against every existing site
        active_list_entities = [e for _, entities in batch.models_by_batch_key.items() for e in entities]
        deleted_list_entities = [e for _, entities in batch.deleted_by_batch_key.items() for e in entities]
        active_agg_site_group_ids = [
            (e.aggregator_id, e.site_id, e.original.site_control_group_id) for e in active_list_entities
        ]
        deleted_agg_site_group_ids = [
            (e.aggregator_id, e.site_id, e.original.site_control_group_id) for e in deleted_list_entities
        ]

        for expected_site_agg_tuple, expected_group_id in zip(expected_site_agg_ids, expected_active_default_ids):
            expected_tuple = (expected_site_agg_tuple[0], expected_site_agg_tuple[1], expected_group_id)
            assert expected_tuple in active_agg_site_group_ids

        for expected_site_agg_tuple, expected_group_id in zip(expected_site_agg_ids, expected_deleted_default_ids):
            expected_tuple = (expected_site_agg_tuple[0], expected_site_agg_tuple[1], expected_group_id)
            assert expected_tuple in deleted_agg_site_group_ids

        # Validate the deleted entities are the ones we expect (lean on the fact we setup a property on the
        # archive type in a particular way for the expected matches)
        assert all(
            [
                e.original.primacy == e.original.site_control_group_id
                for v_list in batch.deleted_by_batch_key.values()
                for e in v_list
            ]
        )

        # Sanity check that a different timestamp yields nothing
        empty_batch = await fetch_sites_by_changed_at(session, timestamp - timedelta(milliseconds=50))
        assert_batched_entities(
            empty_batch, ControlGroupScopedDefaultSiteControl, ArchiveControlGroupScopedDefaultSiteControl, 0, 0
        )
        assert len(empty_batch.models_by_batch_key) == 0
        assert len(empty_batch.deleted_by_batch_key) == 0
