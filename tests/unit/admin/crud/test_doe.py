from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import func, select

from envoy.admin.crud.doe import (
    count_all_does,
    count_all_site_control_groups,
    delete_does_with_start_time_in_range,
    select_all_does,
    select_all_site_control_groups,
    upsert_many_doe,
)
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup


async def _select_latest_dynamic_operating_envelope(session) -> DynamicOperatingEnvelope:
    stmt = (
        select(DynamicOperatingEnvelope)
        .order_by(DynamicOperatingEnvelope.dynamic_operating_envelope_id.desc())
        .limit(1)
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


@pytest.mark.anyio
async def test_upsert_many_doe_inserts(pg_base_config):
    """Assert that we are able to successfully insert a valid DOERequest into a db"""
    deleted_time = datetime(2022, 11, 4, 7, 4, 2, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        doe_in: DynamicOperatingEnvelope = generate_class_instance(
            DynamicOperatingEnvelope, generate_relationships=False, site_id=1, site_control_group_id=1
        )
        # clean up generated instance to ensure it doesn't clash with base_config
        del doe_in.dynamic_operating_envelope_id

        await upsert_many_doe(session, [doe_in], deleted_time)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        assert (
            await session.execute(select(func.count()).select_from(ArchiveDynamicOperatingEnvelope))
        ).scalar_one() == 0, "Nothing is archived on insert"
        doe_out = await _select_latest_dynamic_operating_envelope(session)

        assert_class_instance_equality(
            DynamicOperatingEnvelope,
            doe_out,
            doe_in,
            ignored_properties={"dynamic_operating_envelope_id", "created_time"},
        )

        # created_time should be now as this is an insert, changed_time should match what was put in
        assert_nowish(doe_out.created_time)
        assert_datetime_equal(doe_out.changed_time, doe_out.changed_time)

        doe_in_1 = generate_class_instance(
            DynamicOperatingEnvelope,
            site_id=1,
            start_time=doe_in.start_time + timedelta(seconds=1),
            site_control_group_id=1,
        )

        # See if any errors get raised
        await upsert_many_doe(session, [doe_in, doe_in_1], deleted_time)

        # Because the scond upsert included_doe_in again, it will archive the old version
        assert (
            await session.execute(select(func.count()).select_from(ArchiveDynamicOperatingEnvelope))
        ).scalar_one() == 1


@pytest.mark.anyio
async def test_upsert_many_doe_update(pg_base_config):
    """Assert that we are able to successfully update a valid DOERequest in the db"""
    deleted_time = datetime(2022, 11, 4, 7, 4, 2, tzinfo=timezone.utc)
    original_doe_copy: DynamicOperatingEnvelope
    async with generate_async_session(pg_base_config) as session:
        original_doe = await _select_latest_dynamic_operating_envelope(session)
        original_doe_copy = clone_class_instance(original_doe, ignored_properties={"site", "site_control_group"})

        # clean up generated instance to ensure it doesn't clash with base_config
        doe_to_update: DynamicOperatingEnvelope = clone_class_instance(
            original_doe,
            ignored_properties={"dynamic_operating_envelope_id", "created_time", "site", "site_control_group"},
        )
        doe_to_update.export_limit_watts += Decimal("99.1")
        doe_to_update.import_limit_active_watts += Decimal("98.2")
        doe_to_update.changed_time = datetime(2026, 1, 3, tzinfo=timezone.utc)
        doe_to_update.created_time = datetime(2027, 1, 3, tzinfo=timezone.utc)

        await upsert_many_doe(session, [doe_to_update], deleted_time)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        doe_after_update = await _select_latest_dynamic_operating_envelope(session)

        # This is a "new" DOE as it's replacing the old one.
        assert_class_instance_equality(
            DynamicOperatingEnvelope,
            doe_to_update,
            doe_after_update,
            ignored_properties={"dynamic_operating_envelope_id", "created_time", "site", "site_control_group"},
        )
        assert_nowish(doe_after_update.created_time)

        # Archive is filled with the DOE that was updated
        archive_data = (await session.execute(select(ArchiveDynamicOperatingEnvelope))).scalar_one()
        assert_class_instance_equality(
            DynamicOperatingEnvelope,
            original_doe_copy,
            archive_data,
        )
        assert_nowish(archive_data.archive_time)
        assert archive_data.deleted_time == deleted_time


@pytest.mark.parametrize(
    "site_control_group_id, changed_after, expected_count",
    [
        (1, None, 4),
        (1, datetime.min, 4),
        (1, datetime.max, 0),
        (1, datetime(2022, 5, 6, 11, 22, 33, tzinfo=timezone.utc), 4),
        (1, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), 3),
        (1, datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc), 2),
        (1, datetime(2022, 5, 6, 13, 22, 34, tzinfo=timezone.utc), 1),
        (1, datetime(2022, 5, 6, 14, 22, 34, tzinfo=timezone.utc), 0),
        (2, None, 0),
        (2, datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc), 0),
    ],
)
@pytest.mark.anyio
async def test_count_all_does(
    pg_base_config, site_control_group_id: int, changed_after: Optional[datetime], expected_count: int
):
    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_does(session, site_control_group_id, changed_after)) == expected_count


@pytest.mark.parametrize(
    "site_control_group_id, start, limit, after, expected_doe_ids",
    [
        (1, 0, 999, None, [1, 2, 3, 4]),
        (1, 2, 999, None, [3, 4]),
        (1, 0, 2, None, [1, 2]),
        (1, 1, 2, None, [2, 3]),
        (1, 99, 99, None, []),
        (1, 0, 99, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), [2, 3, 4]),
        (1, 1, 99, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), [3, 4]),
        (1, 1, 1, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), [3]),
        (2, 0, 999, None, []),
        (2, 1, 99, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), []),
    ],
)
@pytest.mark.anyio
async def test_select_all_does(
    pg_base_config,
    site_control_group_id: int,
    start: int,
    limit: int,
    after: Optional[datetime],
    expected_doe_ids: list[int],
):
    async with generate_async_session(pg_base_config) as session:
        does = await select_all_does(session, site_control_group_id, start, limit, after)
        assert_list_type(DynamicOperatingEnvelope, does, len(expected_doe_ids))
        assert expected_doe_ids == [d.dynamic_operating_envelope_id for d in does]


@pytest.fixture
async def extra_site_control_groups(pg_base_config):

    # Current database entry has changed time '2021-04-05 10:01:00.500'
    async with generate_async_session(pg_base_config) as session:
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=101,
                primacy=2,
                site_control_group_id=2,
                changed_time=datetime(2021, 4, 5, 10, 2, 0, 500000, tzinfo=timezone.utc),
            )
        )
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=202,
                primacy=1,
                site_control_group_id=3,
                changed_time=datetime(2021, 4, 5, 10, 3, 0, 500000, tzinfo=timezone.utc),
            )
        )
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=303,
                primacy=1,
                site_control_group_id=4,
                changed_time=datetime(2021, 4, 5, 10, 4, 0, 500000, tzinfo=timezone.utc),
            )
        )
        await session.commit()
    yield pg_base_config


@pytest.mark.parametrize(
    "changed_after, expected_count",
    [
        (None, 4),
        (datetime.min, 4),
        (datetime.max, 0),
        (datetime(2021, 4, 5, 10, 1, 0, tzinfo=timezone.utc), 4),
        (datetime(2021, 4, 5, 10, 2, 0, tzinfo=timezone.utc), 3),
        (datetime(2021, 4, 5, 10, 3, 0, tzinfo=timezone.utc), 2),
        (datetime(2021, 4, 5, 10, 4, 0, tzinfo=timezone.utc), 1),
    ],
)
@pytest.mark.anyio
async def test_count_all_site_control_groups(
    extra_site_control_groups, changed_after: Optional[datetime], expected_count: int
):
    async with generate_async_session(extra_site_control_groups) as session:
        assert (await count_all_site_control_groups(session, changed_after)) == expected_count


@pytest.mark.parametrize(
    "start, limit, after, expected_site_control_ids",
    [
        (0, 999, None, [1, 2, 3, 4]),
        (1, 2, None, [2, 3]),
        (0, 999, datetime(2021, 4, 5, 10, 1, 0, tzinfo=timezone.utc), [1, 2, 3, 4]),
        (0, 999, datetime(2021, 4, 5, 10, 2, 0, tzinfo=timezone.utc), [2, 3, 4]),
        (2, 999, datetime(2021, 4, 5, 10, 2, 0, tzinfo=timezone.utc), [4]),
    ],
)
@pytest.mark.anyio
async def test_select_all_site_control_groups(
    extra_site_control_groups,
    start: int,
    limit: int,
    after: Optional[datetime],
    expected_site_control_ids: list[int],
):
    async with generate_async_session(extra_site_control_groups) as session:
        groups = await select_all_site_control_groups(session, start, limit, after)
        assert_list_type(SiteControlGroup, groups, len(expected_site_control_ids))
        assert expected_site_control_ids == [g.site_control_group_id for g in groups]


@pytest.mark.parametrize(
    "site_control_group_id, site_id, period_start, period_end, expected_doe_ids",
    [
        (99, None, datetime.min, datetime.max, []),
        (1, None, datetime.min, datetime.max, [1, 2, 3, 4]),
        (1, 1, datetime.min, datetime.max, [1, 2, 4]),
        (1, 2, datetime.min, datetime.max, [3]),
        (1, 3, datetime.min, datetime.max, []),
        (
            1,
            None,
            datetime(2022, 5, 7, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            datetime(2022, 5, 8, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            [1, 2, 3],
        ),
        (
            1,
            None,
            datetime(2022, 5, 7, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            datetime(2022, 5, 7, 1, 2, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            [1, 3],
        ),
        (
            1,
            1,
            datetime(2022, 5, 7, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            datetime(2022, 5, 8, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            [1, 2],
        ),
        (
            1,
            2,
            datetime(2022, 5, 7, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            datetime(2022, 5, 8, 1, 2, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            [3],
        ),
    ],
)
@pytest.mark.anyio
async def test_delete_does_with_start_time_in_range(
    pg_base_config,
    site_control_group_id: int,
    site_id: Optional[int],
    period_start: datetime,
    period_end: datetime,
    expected_doe_ids: list[int],
):
    """Tests that delete_does_with_start_time_in_range only deletes (and archives) the appropriate DOE controls"""

    # Do the delete
    deleted_time = datetime(2022, 5, 7, 2, 1, 2, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        original_doe_count = (
            await session.execute(select(func.count()).select_from(DynamicOperatingEnvelope))
        ).scalar_one()

        await delete_does_with_start_time_in_range(
            session, site_control_group_id, site_id, period_start, period_end, deleted_time
        )
        await session.commit()

    # Check what got deleted
    async with generate_async_session(pg_base_config) as session:
        after_doe_count = (
            await session.execute(select(func.count()).select_from(DynamicOperatingEnvelope))
        ).scalar_one()
        deleted_does = (
            (
                await session.execute(
                    select(ArchiveDynamicOperatingEnvelope)
                    .where(ArchiveDynamicOperatingEnvelope.deleted_time.is_not(None))
                    .order_by(ArchiveDynamicOperatingEnvelope.dynamic_operating_envelope_id)
                )
            )
            .scalars()
            .all()
        )
        deleted_doe_ids = [d.dynamic_operating_envelope_id for d in deleted_does]
        assert expected_doe_ids == deleted_doe_ids
        assert after_doe_count == (original_doe_count - len(expected_doe_ids))

        # Check they actually deleted
        remaining_does_with_id = (
            await session.execute(
                select(func.count())
                .select_from(DynamicOperatingEnvelope)
                .where(DynamicOperatingEnvelope.dynamic_operating_envelope_id.in_(expected_doe_ids))
            )
        ).scalar_one()
        assert remaining_does_with_id == 0, "These IDs should've been deleted"
