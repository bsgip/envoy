from datetime import datetime, timezone
from itertools import product
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.asserts.type import assert_iterable_type
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.types import QualityFlagsType
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.site_reading import (
    count_site_reading_types_for_aggregator,
    delete_site_reading_type_for_aggregator,
    fetch_site_reading_type_for_aggregator,
    fetch_site_reading_types_page_for_aggregator,
    upsert_site_reading_type_for_aggregator,
    upsert_site_readings,
)
from envoy.server.manager.time import utc_now
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from tests.unit.server.crud.test_end_device import SnapshotTableCount, count_table_rows


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
    "aggregator_id, site_id, site_reading_type_id, expected",
    [
        (
            1,
            None,
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
                role_flags=1,
                changed_time=datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc),
                created_time=datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        ),
        (
            1,
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
                role_flags=1,
                changed_time=datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc),
                created_time=datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        ),
        (
            3,
            None,
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
                role_flags=2,
                changed_time=datetime(2022, 5, 6, 12, 22, 33, 500000, tzinfo=timezone.utc),
                created_time=datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        ),
        (2, None, 1, None),  # Wrong aggregator
        (1, None, 99, None),  # Wrong site_reading_type_id
        (1, 99, 1, None),  # Wrong site_id
        (1, 2, 1, None),  # Wrong site_id
    ],
)
@pytest.mark.anyio
async def test_fetch_site_reading_type_for_aggregator(
    pg_base_config,
    aggregator_id: int,
    site_id: Optional[int],
    site_reading_type_id: int,
    expected: Optional[SiteReadingType],
):
    """Tests the contents of the returned SiteReadingType"""
    for include_site_relation in [True, False]:
        async with generate_async_session(pg_base_config) as session:
            actual = await fetch_site_reading_type_for_aggregator(
                session, aggregator_id, site_reading_type_id, site_id, include_site_relation=include_site_relation
            )
            assert_class_instance_equality(SiteReadingType, expected, actual, ignored_properties=set(["site"]))


@pytest.mark.anyio
async def test_fetch_site_reading_type_for_aggregator_relationship(pg_base_config):
    """Tests the relationship fetching behaviour"""
    async with generate_async_session(pg_base_config) as session:
        # test with no site relation (ensure raise loading is enabled)
        actual_no_relation = await fetch_site_reading_type_for_aggregator(
            session, 1, 1, None, include_site_relation=False
        )
        with pytest.raises(Exception):
            actual_no_relation.site.lfdi

        # Test site relation can be navigated for different sites
        actual_with_relation = await fetch_site_reading_type_for_aggregator(
            session, 1, 1, None, include_site_relation=True
        )
        assert actual_with_relation.site.lfdi == "site1-lfdi"

        actual_4_with_relation = await fetch_site_reading_type_for_aggregator(
            session, 1, 4, None, include_site_relation=True
        )
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
            SiteReadingType, new_srt, actual_srt, ignored_properties={"site_reading_type_id", "created_time"}
        )
        assert_nowish(actual_srt.created_time)

        # This is an inserted row - nothing should be added to the archive
        assert (await session.execute(select(func.count()).select_from(ArchiveSiteReadingType))).scalar_one() == 0


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
        srt_to_upsert.role_flags = existing_srt.role_flags

    # Perform the upsert in a new session
    async with generate_async_session(pg_base_config) as session:
        updated_id = await upsert_site_reading_type_for_aggregator(session, aggregator_id, srt_to_upsert)
        assert updated_id == srt_id_to_update
        await session.commit()

    # Validate the state of the DB in a new session
    async with generate_async_session(pg_base_config) as session:
        # check it exists
        actual_srt = await fetch_site_reading_type(session, aggregator_id, srt_id_to_update)
        assert_class_instance_equality(
            SiteReadingType, srt_to_upsert, actual_srt, {"site_reading_type_id", "created_time"}
        )
        assert_datetime_equal(
            datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc), actual_srt.created_time
        )  # created_time doesn't update

        # Sanity check the count
        assert len(await fetch_site_reading_types(session, aggregator_id)) == 3

        # This is an updated row - therefore we should have a new archived record containing the original data
        assert (await session.execute(select(func.count()).select_from(ArchiveSiteReadingType))).scalar_one() == 1
        archive_data = (await session.execute(select(ArchiveSiteReadingType))).scalar_one()

        # This is comparing the archive data against what was originally in the DB
        if srt_id_to_update == 1:
            assert_class_instance_equality(
                SiteReadingType,
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
                    role_flags=1,
                    created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    changed_time=datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc),
                ),
                archive_data,
            )
        elif srt_id_to_update == 3:
            assert_class_instance_equality(
                SiteReadingType,
                SiteReadingType(
                    site_reading_type_id=3,
                    aggregator_id=1,
                    site_id=1,
                    uom=38,
                    data_qualifier=8,
                    flow_direction=1,
                    accumulation_behaviour=3,
                    kind=37,
                    phase=64,
                    power_of_ten_multiplier=0,
                    default_interval_seconds=3600,
                    role_flags=3,
                    created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                    changed_time=datetime(2022, 5, 6, 13, 22, 33, 500000, tzinfo=timezone.utc),
                ),
                archive_data,
            )
        assert_nowish(archive_data.archive_time)
        assert archive_data.deleted_time is None


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
        update_attempt_srt.changed_time = datetime.now(tz=timezone.utc)

    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(ValueError):
            await upsert_site_reading_type_for_aggregator(session, aggregator_id, update_attempt_srt)

        # db should be unmodified
        db_srt = await fetch_site_reading_type(session, aggregator_id, site_id_to_update)
        assert db_srt
        assert_datetime_equal(db_srt.changed_time, datetime(2022, 5, 6, 11, 22, 33, 500000, tzinfo=timezone.utc))
        assert (await session.execute(select(func.count()).select_from(ArchiveSiteReadingType))).scalar_one() == 0


@pytest.mark.anyio
async def test_upsert_site_readings_mixed_insert_update(pg_base_config):
    """Tests an upsert on site_readings with a mix of inserts/updates"""
    aest = ZoneInfo("Australia/Brisbane")
    deleted_time = datetime(2004, 5, 7, 1, 3, 4, 53151, tzinfo=timezone.utc)
    site_readings: list[SiteReading] = [
        # Insert
        SiteReading(
            site_reading_type_id=1,
            changed_time=datetime(2022, 1, 2, 3, 4, 5, 500000, tzinfo=timezone.utc),
            created_time=datetime(2023, 11, 1, 4, 5, tzinfo=timezone.utc),  # This won't get stored
            local_id=1234,
            quality_flags=QualityFlagsType.VALID,
            time_period_start=datetime(2022, 8, 9, 4, 5, 6, tzinfo=timezone.utc),
            time_period_seconds=456,
            value=789,
        ),
        # Update everything non index
        SiteReading(
            site_reading_type_id=1,  # Index col to match existing
            changed_time=datetime(2022, 6, 7, 8, 9, 10, 500000, tzinfo=timezone.utc),
            created_time=datetime(2023, 11, 1, 4, 5, tzinfo=timezone.utc),  # This won't get stored
            local_id=4567,
            quality_flags=QualityFlagsType.VALID,
            time_period_start=datetime(2022, 6, 7, 2, 0, 0, tzinfo=aest),  # Index col to match existing
            time_period_seconds=27,
            value=-45,
        ),
        # Insert (partial match on unique constraint)
        SiteReading(
            site_reading_type_id=3,  # Won't match existing reading
            changed_time=datetime(2022, 10, 11, 12, 13, 14, 500000, tzinfo=timezone.utc),
            created_time=datetime(2023, 11, 1, 4, 5, tzinfo=timezone.utc),  # This won't get stored
            local_id=111,
            quality_flags=QualityFlagsType.FORECAST,
            time_period_start=datetime(2022, 6, 7, 2, 0, 0, tzinfo=aest),  # Will match existing reading
            time_period_seconds=563,
            value=123,
        ),
    ]

    # Perform the upsert
    async with generate_async_session(pg_base_config) as session:
        await upsert_site_readings(session, deleted_time, site_readings)
        await session.commit()

    # Check the data persisted
    async with generate_async_session(pg_base_config) as session:
        all_db_readings = await fetch_site_readings(session)
        assert len(all_db_readings) == 6, "Two readings inserted - one updated"

        # assert the inserts of the DB
        sr_insert_1 = [sr for sr in all_db_readings if sr.value == 789][0]
        assert_class_instance_equality(
            SiteReading, site_readings[0], sr_insert_1, ignored_properties={"site_reading_id", "created_time"}
        )
        assert_nowish(sr_insert_1.created_time)

        sr_insert_2 = [sr for sr in all_db_readings if sr.value == 123][0]
        assert_class_instance_equality(
            SiteReading, site_readings[2], sr_insert_2, ignored_properties={"site_reading_id", "created_time"}
        )
        assert_nowish(sr_insert_2.created_time)

        # assert the update
        sr_updated = [sr for sr in all_db_readings if sr.value == -45][0]
        assert_class_instance_equality(
            SiteReading, site_readings[1], sr_updated, ignored_properties={"site_reading_id", "created_time"}
        )
        assert_nowish(sr_updated.created_time)

        # Assert other fields are untouched
        sr_1 = all_db_readings[0]
        assert_class_instance_equality(
            SiteReading,
            SiteReading(
                site_reading_id=1,
                site_reading_type_id=1,
                created_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
                changed_time=datetime(2022, 6, 7, 11, 22, 33, 500000, tzinfo=timezone.utc),
                local_id=11111,
                quality_flags=QualityFlagsType.VALID,
                time_period_start=datetime(2022, 6, 7, 1, 0, 0, tzinfo=aest),  # Will match existing reading
                time_period_seconds=300,
                value=11,
            ),
            sr_1,
        ),

        # Check the archive - should've archived the updated record
        archive_records = (await session.execute(select(ArchiveSiteReading))).scalars().all()
        assert len(archive_records) == 1, "Only a single record should've archived"
        assert archive_records[0].site_reading_id == 2, "This is the original value from the DB"
        assert archive_records[0].site_reading_type_id == 1, "This is the original value from the DB"
        assert archive_records[0].local_id == 22222, "This is the original value from the DB"
        assert archive_records[0].time_period_seconds == 300, "This is the original value from the DB"
        assert archive_records[0].deleted_time == deleted_time
        assert_datetime_equal(datetime(2000, 1, 1, tzinfo=timezone.utc), archive_records[0].created_time)
        assert_nowish(archive_records[0].archive_time)


@pytest.mark.parametrize(
    "aggregator_id, site_id, start, limit, after, expected_ids, expected_count",
    [
        (1, None, 0, 99, datetime.min, [1, 3, 4], 3),
        (1, None, 1, 1, datetime.min, [3], 3),
        (1, None, 99, 1, datetime.min, [], 3),
        (1, 1, 0, 99, datetime.min, [1, 3], 2),
        (1, None, 0, 99, datetime(2022, 5, 6, 12, 22, 33, tzinfo=timezone.utc), [3, 4], 2),
        (1, 1, 0, 99, datetime(2022, 5, 6, 12, 22, 33, tzinfo=timezone.utc), [3], 1),
        (99, None, 0, 99, datetime.min, [], 0),  # bad agg id
        (1, 99, 0, 99, datetime.min, [], 0),  # bad site id
        (1, None, 0, 99, datetime(2035, 11, 12), [], 0),  # bad changed after
    ],
)
@pytest.mark.anyio
async def test_fetch_site_reading_type_pages(
    pg_base_config,
    aggregator_id: int,
    site_id: Optional[int],
    start: int,
    limit: int,
    after: datetime,
    expected_ids: list[int],
    expected_count: int,
):
    """Tests the contents of the returned SiteReadingType"""
    async with generate_async_session(pg_base_config) as session:
        actual = await fetch_site_reading_types_page_for_aggregator(
            session, aggregator_id, site_id, start, limit, after
        )
        assert_iterable_type(SiteReadingType, actual, count=len(expected_ids))

        actual_count = await count_site_reading_types_for_aggregator(session, aggregator_id, site_id, after)
        assert actual_count == expected_count


async def snapshot_all_srt_tables(
    session: AsyncSession, agg_id: int, site_id: Optional[int], srt_id: int
) -> list[SnapshotTableCount]:
    """Snapshots the site reading type table and all downstream child tables"""
    snapshot: list[SnapshotTableCount] = []

    snapshot.append(
        await count_table_rows(
            session,
            SiteReadingType,
            None,
            ArchiveSiteReadingType,
            lambda q: q.where(SiteReadingType.aggregator_id == agg_id)
            .where(or_(site_id is None, SiteReadingType.site_id == site_id))
            .where(SiteReadingType.site_reading_type_id == srt_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteReading,
            None,
            ArchiveSiteReading,
            lambda q: q.where(SiteReading.site_reading_type_id == srt_id),
        )
    )

    return snapshot


@pytest.mark.parametrize(
    "agg_id, site_id, srt_id, expected_delete, commit",
    [
        (a, s, i, d, c)
        for (a, s, i, d), c in product(
            [
                (1, 1, 1, True),  # Delete site reading type 1
                (1, None, 1, True),  # Delete site reading type 1
                (3, 1, 2, True),  # Delete site reading type 2
                (3, None, 2, True),  # Delete site reading type 2
                (1, 1, 3, True),  # Delete site reading type 3
                (1, None, 3, True),  # Delete site reading type 3
                (1, 2, 4, True),  # Delete site reading type 4
                (1, None, 4, True),  # Delete site reading type 4
                (0, 1, 1, False),  # Wrong aggregator ID
                (0, None, 1, False),  # Wrong aggregator ID
                (2, 1, 1, False),  # Wrong aggregator ID
                (3, 1, 1, False),  # Wrong aggregator ID
                (99, 1, 1, False),  # Wrong aggregator ID
                (99, None, 1, False),  # Wrong aggregator ID
                (1, 2, 1, False),  # Wrong site ID
                (1, 99, 1, False),  # Wrong site ID
                (1, 1, 99, False),  # Wrong site reading type id
                (1, None, 99, False),  # Wrong site reading type id
            ],
            [True, False],  # Run every test case with a commit = True and commit = False
        )
    ],
)
@pytest.mark.anyio
async def test_delete_site_reading_type_for_site(
    pg_base_config, agg_id: int, site_id: Optional[int], srt_id: int, commit: bool, expected_delete: int
):
    """Tests that deleting an entire site reading type cleans up and archives all associated data correctly. Also tests
    that the operation correctly runs inside a session transaction and can be wound back (if required)

    There is an assumption that the underlying archive functions are used - this is just making sure that
    the removal:
        1) Removes the correct records
        2) Archives the correct records
        3) Doesn't delete anything else it shouldn't
    """

    # Count everything before the delete
    async with generate_async_session(pg_base_config) as session:
        snapshot_before = await snapshot_all_srt_tables(session, agg_id=agg_id, site_id=site_id, srt_id=srt_id)

    # Perform the delete
    now = utc_now()
    deleted_time = datetime(2014, 11, 15, 2, 4, 5, 755, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        actual = await delete_site_reading_type_for_aggregator(session, agg_id, site_id, srt_id, deleted_time)
        assert expected_delete == actual

        if commit:
            await session.commit()
            delete_occurred = actual
        else:
            delete_occurred = False

    # Now check the DB / Archive to ensure everything moved as expected
    async with generate_async_session(pg_base_config) as session:
        snapshot_after = await snapshot_all_srt_tables(session, agg_id=agg_id, site_id=site_id, srt_id=srt_id)

    # Compare our before/after snapshots based on whether a delete occurred (or didn't)
    for before, after in zip(snapshot_before, snapshot_after):
        assert before.t == after.t, "This is a sanity check on snapshot_all_srt_tables doing a consistent order"
        assert before.archive_t == after.archive_t, "This is a sanity check on snapshot_all_srt_tables"
        assert before.archive_count == 0, f"{before.t}: Archive should've been empty at the start"

        if delete_occurred:
            # Check the counts migrated as expected
            assert after.archive_count == before.filtered_count, f"{before.t} All matched records should archive"
            assert after.filtered_count == 0, f"{before.t} All matched records should archive and be removed"
            assert (
                after.total_count == before.total_count - before.filtered_count
            ), f"{before.t} Other records left alone"

            # Check the archive records
            async with generate_async_session(pg_base_config) as session:
                archives: list[ArchiveBase] = (await session.execute(select(after.archive_t))).scalars().all()
                assert all((a.deleted_time == deleted_time for a in archives)), f"{before.t} deleted time is wrong"
                assert all(
                    (abs((a.archive_time - now).seconds) < 20 for a in archives)
                ), f"{before.t} archive time should be nowish"
        else:
            assert after.archive_count == 0, f"{before.t} Nothing should've persisted/deleted"
            assert after.filtered_count == before.filtered_count, f"{before.t} Nothing should've persisted/deleted"
            assert after.total_count == before.total_count, f"{before.t} Nothing should've persisted/deleted"

    async with generate_async_session(pg_base_config) as session:
        srt = await fetch_site_reading_type_for_aggregator(
            session, site_id=site_id, aggregator_id=agg_id, site_reading_type_id=srt_id, include_site_relation=False
        )
        if commit:
            assert srt is None, "SiteReadingType should NOT be fetchable if the deleted was committed"
        elif expected_delete:
            assert srt is not None, "If the delete was NOT committed - the SiteReadingType should still exist"
        else:
            assert (
                srt is None
            ), "If the delete was NOT committed but the SiteReadingType DNE - it should continue to not exist"
