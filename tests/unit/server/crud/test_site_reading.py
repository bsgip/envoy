from datetime import datetime, timezone
from itertools import product
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.asserts.type import assert_iterable_type, assert_list_type
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.types import QualityFlagsType
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.site_reading import (
    GroupedSiteReadingTypeDetails,
    count_grouped_site_reading_details,
    delete_site_reading_type_group,
    fetch_grouped_site_reading_details,
    fetch_site_reading_type_for_mrid,
    fetch_site_reading_types_for_group,
    fetch_site_reading_types_for_group_mrid,
    generate_site_reading_type_group_id,
    upsert_site_readings,
)
from envoy.server.manager.time import utc_now
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from tests.unit.server.crud.test_end_device import SnapshotTableCount, count_table_rows


@pytest.mark.anyio
async def test_generate_site_reading_type_group_id(pg_base_config):
    values: list[int] = []
    async with generate_async_session(pg_base_config) as session:
        values.append(await generate_site_reading_type_group_id(session))
        values.append(await generate_site_reading_type_group_id(session))
        await session.rollback()

    async with generate_async_session(pg_base_config) as session:
        values.append(await generate_site_reading_type_group_id(session))
        values.append(await generate_site_reading_type_group_id(session))
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        values.append(await generate_site_reading_type_group_id(session))
        values.append(await generate_site_reading_type_group_id(session))

    assert len(values) == 6
    assert all((isinstance(v, int) for v in values))
    assert len(values) == len(set(values)), "All distinct values"


@pytest.mark.parametrize(
    "agg_id, site_id, group_id, expected_srt_ids",
    [
        (1, 1, 1, [1, 5]),
        (2, 1, 1, []),
        (1, 3, 1, []),
        (1, 1, 2, []),
        (0, 5, 1, []),
        (1, None, 1, [1, 5]),
        (3, 1, 2, [2]),
        (1, 1, 99, []),
    ],
)
@pytest.mark.anyio
async def test_fetch_site_reading_types_for_group(
    pg_base_config, agg_id: int, site_id: Optional[int], group_id: int, expected_srt_ids: list[int]
):
    async with generate_async_session(pg_base_config) as session:
        results = await fetch_site_reading_types_for_group(session, agg_id, site_id, group_id)
        assert_iterable_type(SiteReadingType, results, len(expected_srt_ids))
        assert [r.site_reading_type_id for r in results] == expected_srt_ids


@pytest.mark.parametrize(
    "agg_id, site_id, group_mrid, expected_srt_ids",
    [
        (1, 1, "10000000000000000000000000000def", [1, 5]),
        (2, 1, "10000000000000000000000000000def", []),
        (1, 3, "10000000000000000000000000000def", []),
        (1, 1, "20000000000000000000000000000def", []),
        (0, 5, "10000000000000000000000000000def", []),
        (1, None, "10000000000000000000000000000def", [1, 5]),
        (3, 1, "20000000000000000000000000000def", [2]),
        (1, 1, "abc123", []),
    ],
)
@pytest.mark.anyio
async def test_fetch_site_reading_types_for_group_mrid(
    pg_base_config, agg_id: int, site_id: Optional[int], group_mrid: int, expected_srt_ids: list[int]
):
    async with generate_async_session(pg_base_config) as session:
        results = await fetch_site_reading_types_for_group_mrid(session, agg_id, site_id, group_mrid)
        assert_iterable_type(SiteReadingType, results, len(expected_srt_ids))
        assert [r.site_reading_type_id for r in results] == expected_srt_ids


def g(group_id: int, group_mrid: str, site_id: int, site_lfdi: str, role_flags: int) -> GroupedSiteReadingTypeDetails:
    """Just to make the test definition a bit more concise"""
    return GroupedSiteReadingTypeDetails(
        group_id=group_id, group_mrid=group_mrid, site_id=site_id, site_lfdi=site_lfdi, role_flags=role_flags
    )


@pytest.mark.parametrize(
    "agg_id, site_id, start, limit, changed_after, expected_groups, expected_count",
    [
        (
            1,
            None,
            0,
            99,
            datetime.min,
            [
                g(1, "10000000000000000000000000000def", 1, "site1-lfdi", 1),
                g(3, "30000000000000000000000000000def", 1, "site1-lfdi", 3),
                g(4, "40000000000000000000000000000def", 2, "site2-lfdi", 4),
            ],
            3,
        ),
        (
            1,
            None,
            1,
            99,
            datetime.min,
            [
                g(3, "30000000000000000000000000000def", 1, "site1-lfdi", 3),
                g(4, "40000000000000000000000000000def", 2, "site2-lfdi", 4),
            ],
            3,
        ),
        (
            1,
            None,
            0,
            2,
            datetime.min,
            [
                g(1, "10000000000000000000000000000def", 1, "site1-lfdi", 1),
                g(3, "30000000000000000000000000000def", 1, "site1-lfdi", 3),
            ],
            3,
        ),
        (
            1,
            1,
            0,
            99,
            datetime.min,
            [
                g(1, "10000000000000000000000000000def", 1, "site1-lfdi", 1),
                g(3, "30000000000000000000000000000def", 1, "site1-lfdi", 3),
            ],
            2,
        ),
        (1, 2, 0, 99, datetime.min, [g(4, "40000000000000000000000000000def", 2, "site2-lfdi", 4)], 1),
        (1, 3, 0, 99, datetime.min, [], 0),
        (2, 1, 0, 99, datetime.min, [], 0),
        (
            1,
            None,
            0,
            99,
            datetime(2022, 5, 6, 14, 22, 33, tzinfo=timezone.utc),
            [
                g(1, "10000000000000000000000000000def", 1, "site1-lfdi", 1),
                g(4, "40000000000000000000000000000def", 2, "site2-lfdi", 4),
            ],
            2,
        ),
        (1, None, 0, 99, datetime(2022, 5, 6, 15, 22, 34, tzinfo=timezone.utc), [], 0),
    ],
)
@pytest.mark.anyio
async def test_fetch_count_grouped_site_reading_details(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    start: int,
    limit: int,
    changed_after: datetime,
    expected_groups: list[GroupedSiteReadingTypeDetails],
    expected_count: int,
):
    async with generate_async_session(pg_base_config) as session:
        actual_groups = await fetch_grouped_site_reading_details(session, agg_id, site_id, start, changed_after, limit)
        assert actual_groups == expected_groups
        assert_list_type(GroupedSiteReadingTypeDetails, actual_groups, len(expected_groups))

        actual_count = await count_grouped_site_reading_details(session, agg_id, site_id, changed_after)
        assert isinstance(actual_count, int)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "agg_id, site_id, mrid, expected_srt_id",
    [
        (1, 1, "10000000000000000000000000000abc", 1),
        (3, 1, "20000000000000000000000000000abc", 2),
        (1, 2, "40000000000000000000000000000abc", 4),
        (2, 1, "10000000000000000000000000000abc", None),
        (1, 2, "10000000000000000000000000000abc", None),
        (1, 1, "20000000000000000000000000000abc", None),
        (1, 1, "200", None),
    ],
)
@pytest.mark.anyio
async def test_fetch_site_reading_type_for_mrid(
    pg_base_config, agg_id: int, site_id: int, mrid: str, expected_srt_id: Optional[int]
):
    async with generate_async_session(pg_base_config) as session:
        actual = await fetch_site_reading_type_for_mrid(session, agg_id, site_id, mrid)
        if expected_srt_id is not None:
            assert isinstance(actual, SiteReadingType)
            assert expected_srt_id == actual.site_reading_type_id
        else:
            assert actual is None


########


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


async def snapshot_all_srt_tables(
    session: AsyncSession, agg_id: int, site_id: Optional[int], srt_ids: list[int]
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
            .where(SiteReadingType.site_reading_type_id.in_(srt_ids)),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteReading,
            None,
            ArchiveSiteReading,
            lambda q: q.where(SiteReading.site_reading_type_id.in_(srt_ids)),
        )
    )

    return snapshot


@pytest.mark.parametrize(
    "agg_id, site_id, group_id, srt_ids, commit",
    [
        (a, s, i, srts, c)
        for (a, s, i, srts), c in product(
            [
                (1, 1, 1, [1, 5]),  # Delete group 1
                (1, None, 1, [1, 5]),  # Delete group 1
                (3, 1, 2, [2]),  # Delete group 2
                (3, None, 2, [2]),  # Delete group 2
                (1, 1, 3, [3]),  # Delete group 3
                (1, None, 3, [3]),  # Delete group 3
                (1, 2, 4, [4]),  # Delete group 4
                (1, None, 4, [4]),  # Delete group 4
                (0, 1, 1, []),  # Wrong aggregator ID
                (0, None, 1, []),  # Wrong aggregator ID
                (2, 1, 1, []),  # Wrong aggregator ID
                (3, 1, 1, []),  # Wrong aggregator ID
                (99, 1, 1, []),  # Wrong aggregator ID
                (99, None, 1, []),  # Wrong aggregator ID
                (1, 2, 1, []),  # Wrong site ID
                (1, 99, 1, []),  # Wrong site ID
                (1, 1, 99, []),  # Wrong site reading type id
                (1, None, 99, []),  # Wrong site reading type id
            ],
            [True, False],  # Run every test case with a commit = True and commit = False
        )
    ],
)
@pytest.mark.anyio
async def test_delete_site_reading_type_group(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    group_id: int,
    srt_ids: list[int],
    commit: bool,
):
    """Tests that deleting an entire site reading type cleans up and archives all associated data correctly. Also tests
    that the operation correctly runs inside a session transaction and can be wound back (if required)

    There is an assumption that the underlying archive functions are used - this is just making sure that
    the removal:
        1) Removes the correct records
        2) Archives the correct records
        3) Doesn't delete anything else it shouldn't
    """
    expected_delete = bool(srt_ids)

    # Count everything before the delete
    async with generate_async_session(pg_base_config) as session:
        snapshot_before = await snapshot_all_srt_tables(session, agg_id=agg_id, site_id=site_id, srt_ids=srt_ids)

    # Perform the delete
    now = utc_now()
    deleted_time = datetime(2014, 11, 15, 2, 4, 5, 755, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        actual = await delete_site_reading_type_group(session, agg_id, site_id, group_id, deleted_time)
        assert expected_delete == actual

        if commit:
            await session.commit()
            delete_occurred = actual
        else:
            delete_occurred = False

    # Now check the DB / Archive to ensure everything moved as expected
    async with generate_async_session(pg_base_config) as session:
        snapshot_after = await snapshot_all_srt_tables(session, agg_id=agg_id, site_id=site_id, srt_ids=srt_ids)

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
        srts = await fetch_site_reading_types_for_group(
            session, site_id=site_id, aggregator_id=agg_id, group_id=group_id
        )
        if commit:
            assert len(srts) == 0, "SiteReadingTypes should NOT be fetchable if the deleted was committed"
        elif expected_delete:
            assert len(srts) == len(srt_ids), "If the delete was NOT committed - the SiteReadingType should still exist"
        else:
            assert (
                len(srts) == 0
            ), "If the delete was NOT committed but the SiteReadingType DNE - it should continue to not exist"
