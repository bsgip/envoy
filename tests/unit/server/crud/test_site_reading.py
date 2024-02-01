from datetime import datetime, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import pytest
from envoy_schema.server.schema.sep2.types import QualityFlagsType
from sqlalchemy import select

from envoy.server.crud.site_reading import (
    fetch_site_reading_type_for_aggregator,
    upsert_site_reading_type_for_aggregator,
    upsert_site_readings,
)
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from tests.assert_time import assert_datetime_equal
from tests.data.fake.generator import assert_class_instance_equality, clone_class_instance, generate_class_instance
from tests.postgres_testing import generate_async_session


async def fetch_site_reading_types(session, aggregator_id: int) -> Sequence[SiteReadingType]:
    stmt = (
        select(SiteReadingType)
        .where((SiteReadingType.aggregator_id == aggregator_id))
        .order_by(SiteReadingType.site_reading_type_id)
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def fetch_site_reading_type(session, aggregator_id: int, site_reading_type_id: int) -> Optional[SiteReadingType]:
    stmt = (
        select(SiteReadingType)
        .where(
            (SiteReadingType.aggregator_id == aggregator_id)
            & (SiteReadingType.site_reading_type_id == site_reading_type_id)
        )
        .order_by(SiteReadingType.site_reading_type_id)
    )

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def fetch_site_readings(session) -> Sequence[SiteReading]:
    stmt = select(SiteReading).order_by(SiteReading.site_reading_id)

    resp = await session.execute(stmt)
    return resp.scalars().all()


@pytest.mark.parametrize(
    "aggregator_id, site_reading_type_id, expected",
    [
        (
            1,
            1,
            SiteReadingType(
                site_reading_type_id=1,
                aggregator_id=1,
                site_id=1,
                uom=38,
                data_qualifier=2,
                flow_direction=1,
                accumulation_behaviour=3,
                kind=37,
                phase=64,
                power_of_ten_multiplier=3,
                default_interval_seconds=0,
                changed_time=datetime(2022, 5, 6, 11, 22, 33, tzinfo=timezone.utc),
            ),
        ),
        (
            3,
            2,
            SiteReadingType(
                site_reading_type_id=2,
                aggregator_id=3,
                site_id=1,
                uom=61,
                data_qualifier=2,
                flow_direction=1,
                accumulation_behaviour=3,
                kind=37,
                phase=64,
                power_of_ten_multiplier=0,
                default_interval_seconds=0,
                changed_time=datetime(2022, 5, 6, 12, 22, 33, tzinfo=timezone.utc),
            ),
        ),
        (2, 1, None),  # Wrong aggregator
        (1, 99, None),  # Wrong site_reading_type_id
    ],
)
@pytest.mark.anyio
async def test_fetch_site_reading_type_for_aggregator(
    pg_base_config, aggregator_id: int, site_reading_type_id: int, expected: Optional[SiteReadingType]
):
    """Tests the contents of the returned SiteReadingType"""
    async with generate_async_session(pg_base_config) as session:
        actual = await fetch_site_reading_type_for_aggregator(
            session, aggregator_id, site_reading_type_id, include_site_relation=False
        )
        assert_class_instance_equality(SiteReadingType, expected, actual, ignored_properties=set(["site"]))


@pytest.mark.anyio
async def test_fetch_site_reading_type_for_aggregator_relationship(pg_base_config):
    """Tests the relationship fetching behaviour"""
    async with generate_async_session(pg_base_config) as session:
        # test with no site relation (ensure raise loading is enabled)
        actual_no_relation = await fetch_site_reading_type_for_aggregator(session, 1, 1, include_site_relation=False)
        with pytest.raises(Exception):
            actual_no_relation.site.lfdi

        # Test site relation can be navigated for different sites
        actual_with_relation = await fetch_site_reading_type_for_aggregator(session, 1, 1, include_site_relation=True)
        assert actual_with_relation.site.lfdi == "site1-lfdi"

        actual_4_with_relation = await fetch_site_reading_type_for_aggregator(session, 1, 4, include_site_relation=True)
        assert actual_4_with_relation.site.lfdi == "site2-lfdi"


@pytest.mark.anyio
async def test_upsert_site_reading_type_for_aggregator_insert(pg_base_config):
    """Tests that the upsert can do inserts"""
    # Do the insert in a session separate to the database
    inserted_id: int
    aggregator_id = 1
    site_id = 1
    new_srt: SiteReadingType = generate_class_instance(SiteReadingType)
    new_srt.aggregator_id = 1
    new_srt.site_id = site_id

    del new_srt.site_reading_type_id  # Don't set the primary key - we expect the DB to set that
    async with generate_async_session(pg_base_config) as session:
        found_srts = await fetch_site_reading_types(session, aggregator_id)
        assert len(found_srts) == 3

        inserted_id = await upsert_site_reading_type_for_aggregator(session, aggregator_id, new_srt)
        assert inserted_id
        await session.commit()

    # Validate the state of the DB in a new session
    async with generate_async_session(pg_base_config) as session:
        found_srts = await fetch_site_reading_types(session, aggregator_id)
        assert len(found_srts) == 4

        actual_srt = found_srts[-1]  # should be the highest ID
        assert_class_instance_equality(
            SiteReadingType, new_srt, actual_srt, ignored_properties=set(["site_reading_type_id"])
        )


@pytest.mark.parametrize("srt_id_to_update, aggregator_id", [(3, 1), (1, 1)])
@pytest.mark.anyio
async def test_upsert_site_reading_type_for_aggregator_non_indexed(
    pg_base_config, srt_id_to_update: int, aggregator_id: int
):
    """Tests that the upsert can do updates to fields that aren't unique constrained"""

    # We want the site object we upsert to be a "fresh" Site instance that hasn't been anywhere near
    # a SQL Alchemy session but shares the appropriate indexed values
    srt_to_upsert: SiteReadingType = generate_class_instance(SiteReadingType)
    async with generate_async_session(pg_base_config) as session:
        existing_srt = await fetch_site_reading_type(session, aggregator_id, srt_id_to_update)
        assert existing_srt

        # Copy across the indexed values as we don't want to update those
        srt_to_upsert.aggregator_id = existing_srt.aggregator_id
        srt_to_upsert.site_id = existing_srt.site_id
        srt_to_upsert.uom = existing_srt.uom
        srt_to_upsert.data_qualifier = existing_srt.data_qualifier
        srt_to_upsert.flow_direction = existing_srt.flow_direction
        srt_to_upsert.accumulation_behaviour = existing_srt.accumulation_behaviour
        srt_to_upsert.kind = existing_srt.kind
        srt_to_upsert.phase = existing_srt.phase
        srt_to_upsert.power_of_ten_multiplier = existing_srt.power_of_ten_multiplier
        srt_to_upsert.default_interval_seconds = existing_srt.default_interval_seconds

    # Perform the upsert in a new session
    async with generate_async_session(pg_base_config) as session:
        updated_id = await upsert_site_reading_type_for_aggregator(session, aggregator_id, srt_to_upsert)
        assert updated_id == srt_id_to_update
        await session.commit()

    # Validate the state of the DB in a new session
    async with generate_async_session(pg_base_config) as session:
        # check it exists
        actual_srt = await fetch_site_reading_type(session, aggregator_id, srt_id_to_update)
        assert_class_instance_equality(SiteReadingType, srt_to_upsert, actual_srt, set(["site_reading_type_id"]))

        # Sanity check the count
        assert len(await fetch_site_reading_types(session, aggregator_id)) == 3


@pytest.mark.anyio
async def test_upsert_site_reading_type_for_aggregator_cant_change_agg_id(pg_base_config):
    """Tests that attempting to sneak through a mismatched agg_id results in an exception with no changes"""
    site_id_to_update = 1
    aggregator_id = 1

    original_srt: SiteReadingType
    update_attempt_srt: SiteReadingType
    async with generate_async_session(pg_base_config) as session:
        original_srt = await fetch_site_reading_type(session, aggregator_id, site_id_to_update)
        assert original_srt

        update_attempt_srt = clone_class_instance(original_srt, ignored_properties=set(["site"]))
        update_attempt_srt.aggregator_id = 3
        update_attempt_srt.changed_time = datetime.utcnow()

    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(ValueError):
            await upsert_site_reading_type_for_aggregator(session, aggregator_id, update_attempt_srt)

        # db should be unmodified
        db_srt = await fetch_site_reading_type(session, aggregator_id, site_id_to_update)
        assert db_srt
        assert_datetime_equal(db_srt.changed_time, datetime(2022, 5, 6, 11, 22, 33, tzinfo=timezone.utc))


@pytest.mark.anyio
async def test_upsert_site_readings_mixed_insert_update(pg_base_config):
    """Tests an upsert on site_readings with a mix of inserts/updates"""
    aest = ZoneInfo("Australia/Brisbane")
    site_readings: list[SiteReading] = [
        # Insert
        SiteReading(
            site_reading_type_id=1,
            changed_time=datetime(2022, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            local_id=1234,
            quality_flags=QualityFlagsType.VALID,
            time_period_start=datetime(2022, 8, 9, 4, 5, 6, tzinfo=timezone.utc),
            time_period_seconds=456,
            value=789,
        ),
        # Update everything non index
        SiteReading(
            site_reading_type_id=1,  # Index col to match existing
            changed_time=datetime(2022, 6, 7, 8, 9, 10, tzinfo=timezone.utc),
            local_id=4567,
            quality_flags=QualityFlagsType.VALID,
            time_period_start=datetime(2022, 6, 7, 2, 0, 0, tzinfo=aest),  # Index col to match existing
            time_period_seconds=27,
            value=-45,
        ),
        # Insert (partial match on unique constraint)
        SiteReading(
            site_reading_type_id=3,  # Won't match existing reading
            changed_time=datetime(2022, 10, 11, 12, 13, 14, tzinfo=timezone.utc),
            local_id=111,
            quality_flags=QualityFlagsType.FORECAST,
            time_period_start=datetime(2022, 6, 7, 2, 0, 0, tzinfo=aest),  # Will match existing reading
            time_period_seconds=563,
            value=123,
        ),
    ]

    # Perform the upsert
    async with generate_async_session(pg_base_config) as session:
        await upsert_site_readings(session, site_readings)
        await session.commit()

    # Check the data persisted
    async with generate_async_session(pg_base_config) as session:
        all_db_readings = await fetch_site_readings(session)
        assert len(all_db_readings) == 6, "Two readings inserted - one updated"

        # assert the inserts of the DB
        sr_5 = all_db_readings[-2]
        assert_class_instance_equality(SiteReading, site_readings[0], sr_5, ignored_properties=set(["site_reading_id"]))

        sr_6 = all_db_readings[-1]
        assert_class_instance_equality(SiteReading, site_readings[2], sr_6, ignored_properties=set(["site_reading_id"]))

        # assert the update
        sr_2 = all_db_readings[1]
        assert_class_instance_equality(SiteReading, site_readings[1], sr_2, ignored_properties=set(["site_reading_id"]))

        # Assert other fields are untouched
        sr_1 = all_db_readings[0]
        assert_class_instance_equality(
            SiteReading,
            SiteReading(
                site_reading_id=1,
                site_reading_type_id=1,
                changed_time=datetime(2022, 6, 7, 11, 22, 33, tzinfo=timezone.utc),
                local_id=11111,
                quality_flags=QualityFlagsType.VALID,
                time_period_start=datetime(2022, 6, 7, 1, 0, 0, tzinfo=aest),  # Will match existing reading
                time_period_seconds=300,
                value=11,
            ),
            sr_1,
        ),
