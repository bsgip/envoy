import json
from datetime import datetime, timezone
from typing import Optional, Sequence

import pytest
from sqlalchemy import select

from envoy.server.crud.site_reading import upsert_site_reading_type_for_aggregator
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.schema.sep2.types import DeviceCategory
from tests.assert_time import assert_datetime_equal
from tests.assert_type import assert_list_type
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


@pytest.mark.anyio
async def test_upsert_site_reading_type_for_aggregator_non_indexed(pg_base_config):
    """Tests that the upsert can do updates to fields that aren't unique constrained"""

    # We want the site object we upsert to be a "fresh" Site instance that hasn't been anywhere near
    # a SQL Alchemy session but shares the appropriate indexed values
    srt_id_to_update = 3
    aggregator_id = 1
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

        # Sanity check another site reading type in the same aggregator
        srt_1 = await fetch_site_reading_type(session, aggregator_id, 1)
        assert_datetime_equal(srt_1.changed_time, datetime(2022, 5, 6, 11, 22, 33, tzinfo=timezone.utc))

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

        update_attempt_srt = clone_class_instance(original_srt)
        update_attempt_srt.aggregator_id = 3
        update_attempt_srt.changed_time = datetime.utcnow()

    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(ValueError):
            await upsert_site_reading_type_for_aggregator(session, aggregator_id, update_attempt_srt)

        # db should be unmodified
        db_srt = await fetch_site_reading_type(session, aggregator_id, site_id_to_update)
        assert db_srt
        assert_datetime_equal(db_srt.changed_time, datetime(2022, 5, 6, 11, 22, 33, tzinfo=timezone.utc))
