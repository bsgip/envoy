from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal
from assertical.asserts.type import assert_dict_type, assert_list_type
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import select, update
from sqlalchemy.exc import InvalidRequestError

from envoy.admin.crud.doe import cancel_then_insert_does
from envoy.server.crud.doe import (
    count_active_does_include_deleted,
    count_does_at_timestamp,
    count_site_control_groups,
    count_site_control_groups_by_fsa_id,
    select_active_does_include_deleted,
    select_doe_by_display_id_include_deleted,
    select_doe_include_deleted,
    select_does_at_timestamp,
    select_site_control_group_by_id,
    select_site_control_group_fsa_ids,
    select_site_control_groups,
)
from envoy.server.crud.site_group import fetch_site_group_membership
from envoy.server.manager.time import utc_now
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope as ArchiveDOE
from envoy.server.model.doe import DynamicOperatingEnvelope as DOE
from envoy.server.model.doe import SiteControlGroup

AEST = ZoneInfo("Australia/Brisbane")


def assert_doe_for_id(
    expected_doe_id: int | None,
    expected_site_group_id: int | None,
    expected_datetime: datetime | None,
    actual_doe: ArchiveDOE | DOE | None,
    check_duration_seconds: bool = True,
):
    """Asserts the supplied doe matches the expected values for a doe with that id. These values are based
    purely on the data patterns in base_config.sql"""
    if expected_doe_id is None:
        assert actual_doe is None
    else:
        assert actual_doe is not None

        # This is just by convention
        if actual_doe.dynamic_operating_envelope_id in {18, 19, 20}:
            assert isinstance(actual_doe, ArchiveDOE)
        else:
            assert isinstance(actual_doe, DOE)

        assert actual_doe.dynamic_operating_envelope_id == expected_doe_id
        assert expected_site_group_id is None or actual_doe.site_group_id == expected_site_group_id
        assert actual_doe.site_control_group_id == 1
        if check_duration_seconds:
            assert actual_doe.duration_seconds == 10 * expected_doe_id + expected_doe_id
        assert actual_doe.import_limit_active_watts == Decimal(f"{expected_doe_id}.11")
        assert actual_doe.export_limit_watts == Decimal(f"-{expected_doe_id}.22")
        if expected_doe_id == 2:
            assert actual_doe.superseded is True
            assert actual_doe.generation_limit_active_watts is None
            assert actual_doe.load_limit_active_watts is None
            assert actual_doe.set_point_percentage is None
            assert actual_doe.ramp_time_seconds is None
        else:
            assert actual_doe.superseded is False
            assert actual_doe.generation_limit_active_watts == Decimal(f"{expected_doe_id}.33")
            assert actual_doe.load_limit_active_watts == Decimal(f"-{expected_doe_id}.44")
            assert actual_doe.set_point_percentage == Decimal(f"{expected_doe_id}.55")
            assert actual_doe.ramp_time_seconds == Decimal(f"{expected_doe_id}.66")

        # This is also by convention
        if actual_doe.dynamic_operating_envelope_id in {1, 3, 4}:
            assert actual_doe.randomize_start_seconds == (
                100 * expected_doe_id + 10 * expected_doe_id + expected_doe_id
            )
        else:
            assert actual_doe.randomize_start_seconds is None

        assert actual_doe.end_time == actual_doe.start_time + timedelta(seconds=actual_doe.duration_seconds)

        assert actual_doe.start_time.tzinfo is not None, "Should be TZ aware"
        assert actual_doe.end_time.tzinfo is not None, "Should be TZ aware"
        if expected_datetime:
            assert expected_datetime.tzinfo is not None, "Should be TZ aware"
            assert_datetime_equal(actual_doe.start_time, expected_datetime)


@pytest.mark.parametrize(
    "agg_id, site_id, doe_id, expected_dt",
    [
        (1, 1, 5, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)),
        (2, 3, 15, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),
        (1, 1, 18, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)),  # Archive record
        (1, 1, 19, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),  # Archive record
        (1, 1, 21, None),  # Archive record (but not deleted)
        (1, 3, 15, None),
        (0, 1, 1, None),
        (2, 1, 15, None),
        (1, 1, 99, None),
        (1, 99, 5, None),
    ],
)
@pytest.mark.anyio
async def test_select_doe_include_deleted(
    pg_additional_does,
    agg_id: int,
    site_id: int,
    doe_id: int,
    expected_dt: datetime | None,
):
    async with generate_async_session(pg_additional_does) as session:
        actual = await select_doe_include_deleted(session, agg_id, site_id, doe_id)
        if expected_dt is None:
            expected_id = None
        else:
            expected_id = doe_id
        assert_doe_for_id(expected_id, None, expected_dt, actual, check_duration_seconds=False)


@pytest.mark.parametrize(
    "agg_id, site_id, display_id, expected_dt",
    [
        (1, 1, 50, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)),
        (2, 3, 150, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),
        (1, 1, 180, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)),  # Archive record
        (1, 1, 190, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),  # Archive record
        (1, 2, 50, None),  # wrong site id
        (1, 1, 210, None),  # Archive record (but not deleted)
        (1, 3, 150, None),
        (0, 1, 10, None),
        (2, 1, 150, None),
        (1, 1, 999, None),
        (1, 99, 50, None),
    ],
)
@pytest.mark.anyio
async def test_select_doe_by_display_id_include_deleted(
    pg_additional_does,
    agg_id: int,
    site_id: int,
    display_id: int,
    expected_dt: datetime | None,
):
    # We are going to munge the display_id to be 10x the PK so we have values
    async with generate_async_session(pg_additional_does) as session:
        await session.execute(update(DOE).values(display_id=DOE.dynamic_operating_envelope_id * 10))
        await session.execute(update(ArchiveDOE).values(display_id=ArchiveDOE.dynamic_operating_envelope_id * 10))
        await session.commit()

    async with generate_async_session(pg_additional_does) as session:
        actual = await select_doe_by_display_id_include_deleted(session, agg_id, site_id, display_id)
        if expected_dt is None:
            expected_id = None
        else:
            expected_id = int(display_id / 10)
        assert_doe_for_id(expected_id, None, expected_dt, actual, check_duration_seconds=False)


@pytest.mark.anyio
async def test_select_and_count_active_does_empty_site_groups(pg_additional_does):
    """Tests out that passing an empty site_group_ids value to the count/select functions returns nothing"""

    now = datetime(2022, 11, 4, tzinfo=UTC)
    after = datetime.min
    async with generate_async_session(pg_additional_does) as session:
        result = await select_active_does_include_deleted(session, 1, set(), now, 0, after, 99)
        assert len(result) == 0

        assert (await count_active_does_include_deleted(session, 1, set(), now, after)) == 0


@pytest.mark.parametrize(
    "expected_ids, expected_count, start, after, limit",
    [
        ([1, 2, 4, 18, 5, 9, 19, 6, 7, 8], 10, 0, datetime.min, 99),
        ([1], 10, 0, datetime.min, 1),
        ([4, 18, 5], 10, 2, datetime.min, 3),
        ([], 10, 0, datetime.min, 0),
        ([], 10, 99, datetime.min, 99),
        ([2, 4, 18, 5, 9, 19, 6, 7, 8], 9, 0, datetime(2022, 5, 6, 12, 22, 32, tzinfo=UTC), 99),
        ([18, 5, 19, 6, 7, 8], 6, 0, datetime(2023, 5, 6, 11, 22, 32, tzinfo=UTC), 99),
        ([5, 19], 6, 1, datetime(2023, 5, 6, 11, 22, 32, tzinfo=UTC), 2),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_active_does_include_deleted_pagination(
    pg_additional_does, expected_ids: list[int], expected_count: int, start: int, after: datetime, limit: int
):
    """Tests out the basic pagination features"""
    now = datetime(1970, 1, 1, 0, 0, 0)  # This is sufficiently in this past to allow everything to pass
    site_control_group_ids = {2}
    site_control_group_id = 1

    async with generate_async_session(pg_additional_does) as session:
        does = await select_active_does_include_deleted(
            session, site_control_group_id, site_control_group_ids, now, start, after, limit
        )
        count = await count_active_does_include_deleted(
            session, site_control_group_id, site_control_group_ids, now, after
        )
        assert len(does) == len(expected_ids)
        assert count == expected_count
        for id, doe in zip(expected_ids, does, strict=False):
            assert_doe_for_id(id, 2, None, doe, check_duration_seconds=False)


@pytest.mark.parametrize(
    "expected_ids, site_control_group_id,  site_group_ids, now",
    [
        ([1, 2, 4, 18, 5, 9, 19, 6, 7, 8], 1, {1, 2}, datetime.min),
        ([3, 20, 10, 11, 12, 13], 1, {1, 4}, datetime.min),
        ([18, 5, 9, 19, 6, 7, 8], 1, {1, 2}, datetime(2023, 5, 7, 0, 59, 59, tzinfo=AEST)),  # Before start
        ([18, 5, 9, 19, 6, 7, 8], 1, {1, 2}, datetime(2023, 5, 7, 1, 4, 59, tzinfo=AEST)),  # Before end
        ([9, 19, 6, 7, 8], 1, {1, 2}, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),  # On expiry time
        ([18, 5, 9, 19, 6, 7, 8], 1, {1, 2}, datetime(2023, 5, 7, 0, 59, 59, tzinfo=AEST)),  # Before start
        ([], 1, {1, 2}, datetime(2045, 1, 1, 0, 0, 0, tzinfo=AEST)),  # Everything expired
        ([], 99, set(), datetime.min),  # empty site groups
    ],
)
@pytest.mark.anyio
async def test_select_and_count_active_does_include_deleted_filtered(
    pg_additional_does,
    site_control_group_id: int,
    expected_ids: list[int],
    site_group_ids: set[int],
    now: datetime,
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_additional_does) as session:
        does = await select_active_does_include_deleted(
            session, site_control_group_id, site_group_ids, now, 0, datetime.min, 99
        )
        count = await count_active_does_include_deleted(
            session, site_control_group_id, site_group_ids, now, datetime.min
        )
        assert isinstance(count, int)

        assert expected_ids == [d.dynamic_operating_envelope_id for d in does]
        assert len(does) == count

        for doe_id, doe in zip(expected_ids, does, strict=False):
            assert_doe_for_id(doe_id, None, None, doe, check_duration_seconds=False)


@pytest.mark.parametrize(
    "expected_ids, site_control_group_id, agg_id, site_id, now",
    [
        ([1, 2, 4], 1, 1, 1, datetime.min),
        ([18, 5, 9, 19, 6, 7, 8], 2, 1, 1, datetime.min),
        ([3, 20], 1, 1, 2, datetime.min),
        ([10, 11, 12, 13], 2, 1, 2, datetime.min),
        ([], 99, 1, 2, datetime.min),
        ([], 1, 1, 1, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),  # On expiry time
        ([9, 19, 6, 7, 8], 2, 1, 1, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),  # On expiry time
    ],
)
@pytest.mark.anyio
async def test_select_and_count_active_does_include_deleted_multiple_groups(
    pg_additional_does, site_control_group_id: int, expected_ids: list[int], agg_id: int, site_id: int, now: datetime
):
    """Tests out the basic filters when half of the DOEs have been split into a different control group"""

    # Migrate ever
    async with generate_async_session(pg_additional_does) as session:
        await session.execute(
            update(DOE)
            .values(site_control_group_id=2)
            .where(DOE.dynamic_operating_envelope_id >= 5)
            .where(DOE.dynamic_operating_envelope_id < 20)
        )
        await session.execute(
            update(ArchiveDOE)
            .values(site_control_group_id=2)
            .where(ArchiveDOE.dynamic_operating_envelope_id >= 5)
            .where(ArchiveDOE.dynamic_operating_envelope_id < 20)
        )
        await session.commit()

    async with generate_async_session(pg_additional_does) as session:
        site_group_ids = await fetch_site_group_membership(session, site_id=site_id, aggregator_id=agg_id)
        assert site_group_ids is not None

        does = await select_active_does_include_deleted(
            session, site_control_group_id, site_group_ids, now, 0, datetime.min, 99
        )
        count = await count_active_does_include_deleted(
            session, site_control_group_id, site_group_ids, now, datetime.min
        )
        assert isinstance(count, int)

        assert expected_ids == [d.dynamic_operating_envelope_id for d in does]
        assert len(does) == count

        for doe_id, doe in zip(expected_ids, does, strict=False):
            assert doe.dynamic_operating_envelope_id == doe_id
            assert doe.site_control_group_id == site_control_group_id


@pytest.mark.anyio
async def test_select_active_does_include_deleted_via_roundtrip(pg_base_config):
    """Tests that DOEs selected via select_active_does_include_deleted match the values inserted via the admin
    server endpoints. This should ensure that the models are being correctly selected (i.e. no missing columns)."""

    # Start by inserting a control that we intend to delete
    now = utc_now()
    start_time_to_delete = now - timedelta(seconds=1)
    duration_seconds = 300
    end_time_to_delete = start_time_to_delete + timedelta(seconds=duration_seconds)
    doe_to_delete = generate_class_instance(
        DOE,
        seed=101,
        dynamic_operating_envelope_id=None,
        start_time=start_time_to_delete,
        duration_seconds=duration_seconds,
        calculation_log_id=None,
        end_time=end_time_to_delete,
        site_group_id=2,
        site_control_group_id=1,
        site_control_group=None,
    )
    async with generate_async_session(pg_base_config) as session:
        site_control_group = (
            await session.execute(select(SiteControlGroup).where(SiteControlGroup.site_control_group_id == 1))
        ).scalar_one()

        cloned_doe = clone_class_instance(doe_to_delete)
        cloned_doe.site_control_group = site_control_group

        session.add(cloned_doe)
        await session.commit()

    # Now we plan on inserting two DOEs - one to replace the DOE we just inserted, the other will be brand new
    doe_to_replace = generate_class_instance(
        DOE,
        seed=202,
        start_time=start_time_to_delete,
        duration_seconds=duration_seconds,
        end_time=end_time_to_delete,
        site_group_id=2,
        site_control_group_id=1,
        calculation_log_id=None,
    )
    doe_to_insert = generate_class_instance(
        DOE,
        seed=303,
        start_time=start_time_to_delete - timedelta(seconds=1),
        duration_seconds=duration_seconds,
        end_time=end_time_to_delete - timedelta(seconds=1),
        site_group_id=2,
        site_control_group_id=1,
        calculation_log_id=None,
    )
    async with generate_async_session(pg_base_config) as session:
        await cancel_then_insert_does(session, [doe_to_replace, doe_to_insert], now)
        await session.commit()

    # Now refetch everything using select_active_does_include_deleted - This will include three DOEs consisting of:
    # the archived doe_to_delete
    # the active doe_to_replace
    # the active doe_to_insert
    async with generate_async_session(pg_base_config) as session:
        site_group_ids = {2}

        results = await select_active_does_include_deleted(session, 1, site_group_ids, now, 0, datetime.min, 99)
        assert len(results) == 3
        archive_does = [r for r in results if isinstance(r, ArchiveDOE)]
        assert len(archive_does) == 1
        active_does = [r for r in results if isinstance(r, DOE)]
        assert len(active_does) == 2

        # Lets make sure everything round tripped OK - the ordering here is guaranteed by the start_time
        assert_class_instance_equality(
            DOE,  # We compare this on DOE as we don't care about the archive specific columns
            doe_to_delete,
            archive_does[0],
            ignored_properties={"changed_time", "created_time", "dynamic_operating_envelope_id"},
        )
        assert_class_instance_equality(
            DOE,
            doe_to_insert,
            active_does[0],
            ignored_properties={"changed_time", "created_time", "dynamic_operating_envelope_id"},
        )
        assert_class_instance_equality(
            DOE,
            doe_to_replace,
            active_does[1],
            ignored_properties={"changed_time", "created_time", "dynamic_operating_envelope_id"},
        )


@pytest.mark.parametrize(
    "expected_id_group_and_starts, timestamp, site_control_group_id, site_group_ids",
    [
        (
            [(5, 2, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST))],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST),
            1,
            {1, 2},
        ),  # For all site 1 groups at timestamp
        (
            [],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST),
            1,
            {},
        ),  # For no groups at timestamp
        (
            [(5, 2, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)), (9, 2, datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST))],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST),
            1,
            {1, 2},
        ),  # overlaps multiple DOEs
        (
            [
                (14, 5, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)),
                (10, 4, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)),
                (5, 2, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)),
                (9, 2, datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST)),
            ],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST),
            1,
            {1, 2, 3, 4, 5, 99},
        ),  # For all groups
        (
            [(5, 2, datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST)), (9, 2, datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST))],
            datetime(2023, 5, 7, 1, 3, 22, tzinfo=AEST),
            1,
            {1, 2},
        ),
        (
            [(9, 2, datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST)), (6, 2, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST))],
            datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST),
            1,
            {1, 2},
        ),
        (
            [(7, 2, datetime(2023, 5, 7, 1, 10, 0, tzinfo=AEST))],
            datetime(2023, 5, 7, 1, 10, 0, tzinfo=AEST),
            1,
            {1, 2},
        ),
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST), 2, {99}),  # Wrong group id
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=AEST), 2, {1, 2}),  # Wrong site control id
        # Throw the timestamp timezone off
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")), 1, {1, 2}),
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")), 1, {1, 2}),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_for_timestamp_filters(
    pg_additional_does,
    expected_id_group_and_starts: list[tuple[int, int, datetime]],
    timestamp: datetime,
    site_control_group_id: int,
    site_group_ids: set[int],
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_additional_does) as session:
        does = await select_does_at_timestamp(
            session, site_control_group_id, site_group_ids, timestamp, 0, datetime.min, 99
        )
        count = await count_does_at_timestamp(session, site_control_group_id, site_group_ids, timestamp, datetime.min)
        assert isinstance(count, int)
        assert len(does) == len(expected_id_group_and_starts)
        assert len(does) == count
        for (id, site_group_id, expected_datetime), doe in zip(expected_id_group_and_starts, does, strict=False):
            assert_doe_for_id(id, site_group_id, expected_datetime, doe, check_duration_seconds=False)


@pytest.mark.parametrize(
    "expected_ids, timestamp, start, after, limit",
    [
        # Start
        ([5, 9], datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST), 0, datetime.min, 99),
        ([9], datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST), 1, datetime.min, 99),
        ([], datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST), 2, datetime.min, 99),
        # Limit
        ([5], datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST), 0, datetime.min, 1),
        ([], datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST), 0, datetime.min, 0),
        # After
        (
            [5, 9],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST),
            0,
            datetime(2023, 2, 3, 11, 22, 32, tzinfo=UTC),
            99,
        ),
        (
            [5],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST),
            0,
            datetime(2023, 2, 3, 11, 22, 34, tzinfo=UTC),
            99,
        ),
        (
            [],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=AEST),
            0,
            datetime(2023, 5, 6, 11, 22, 34, tzinfo=UTC),
            99,
        ),
    ],
)
@pytest.mark.anyio
async def test_select_doe_at_timestamp_pagination(
    pg_additional_does, expected_ids: list[int], timestamp: datetime, start: int, after: datetime, limit: int
):
    """Tests out the basic pagination features for a timestamp that has 2 overlapping DOEs"""
    async with generate_async_session(pg_additional_does) as session:
        does = await select_does_at_timestamp(session, 1, {2}, timestamp, start, after, limit)
        assert len(does) == len(expected_ids)
        for id, doe in zip(expected_ids, does, strict=False):
            assert_doe_for_id(id, 2, None, doe, check_duration_seconds=False)


@pytest.fixture
async def extra_site_control_groups(pg_base_config):

    # Current database entry has changed time '2021-04-05 10:01:00.500'
    #
    # We will slot this in between 1 and 2
    async with generate_async_session(pg_base_config) as session:
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=101,
                primacy=1,
                site_control_group_id=4,
                fsa_id=3,
                required_site_group_id=None,
                changed_time=datetime(2021, 4, 5, 10, 4, 0, 500000, tzinfo=UTC),
            )
        )
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=202,
                primacy=1,
                site_control_group_id=5,
                fsa_id=None,
                required_site_group_id=None,
                changed_time=datetime(2021, 4, 5, 10, 4, 0, 500000, tzinfo=UTC),
            )
        )
        await session.commit()
    yield pg_base_config


@pytest.mark.parametrize(
    "site_control_group_id, expected_primacy, expected_default_import_limit_active_watts",
    [
        (1, 0, Decimal("10.10")),
        (2, 1, None),
        (3, 2, Decimal("20.20")),
        (99, None, None),
        (None, None, None),
    ],
)
@pytest.mark.anyio
async def test_select_site_control_group_by_id(
    extra_site_control_groups,
    site_control_group_id: int,
    expected_primacy: int | None,
    expected_default_import_limit_active_watts: Decimal | None,
):
    """Tests that select_site_control_group_by_code works with a variety of success/failure cases"""

    # With include
    async with generate_async_session(extra_site_control_groups) as session:
        result = await select_site_control_group_by_id(session, site_control_group_id, include_default=True)

        if expected_primacy is None:
            assert result is None
        else:
            assert isinstance(result, SiteControlGroup)
            assert result.primacy == expected_primacy
            assert result.site_control_group_id == site_control_group_id
            if expected_default_import_limit_active_watts is None:
                assert (
                    result.site_control_group_default is None
                    or result.site_control_group_default.import_limit_active_watts is None
                )
            else:
                assert (
                    result.site_control_group_default is not None
                    and result.site_control_group_default.import_limit_active_watts
                    == expected_default_import_limit_active_watts
                )

    # Without include
    async with generate_async_session(extra_site_control_groups) as session:
        result = await select_site_control_group_by_id(session, site_control_group_id, include_default=False)
        if expected_primacy is None:
            assert result is None
        else:
            with pytest.raises(InvalidRequestError):
                result.site_control_group_default.created_time  # ty:ignore[missing-union-attribute]  # noqa: B018


@pytest.mark.parametrize(
    "start, limit, changed_after, fsa_id, scg_restrictions, site_group_ids, expected_ids, expected_count",
    [
        (0, 99, datetime.min, None, {}, {2, 4}, [1, 5, 4, 2, 3], 5),  # no site_group restrictions in this test
        (0, 99, datetime.min, None, {}, {99, 1}, [1, 5, 4, 2, 3], 5),  # no site_group restrictions in this test
        (0, 99, datetime.min, None, {}, set(), [1, 5, 4, 2, 3], 5),  # no site_group restrictions in this test
        (0, 99, datetime.min, None, {1: 2, 2: 4}, set(), [5, 4, 3], 3),
        (0, 99, datetime.min, None, {1: 2, 2: 4}, {2, 4, 99}, [1, 5, 4, 2, 3], 5),
        (0, 99, datetime.min, None, {1: 2, 2: 4}, {2, 99}, [1, 5, 4, 3], 4),
        (0, 99, datetime.min, 1, {}, set(), [1, 2, 3], 3),
        (0, 99, datetime.min, 2, {}, set(), [], 0),
        (0, 99, datetime.min, 3, {}, set(), [4], 1),
        (1, 2, datetime.min, None, {}, set(), [5, 4], 5),
        (1, 1, datetime.min, 1, {}, set(), [2], 3),
        (99, 99, datetime.min, None, {}, set(), [], 5),
        (0, 99, datetime(2021, 4, 5, 10, 1, 0, tzinfo=UTC), None, {}, set(), [1, 5, 4, 2, 3], 5),
        (3, 99, datetime(2021, 4, 5, 10, 1, 0, tzinfo=UTC), None, {}, set(), [2, 3], 5),
        (0, 99, datetime(2021, 4, 5, 10, 2, 0, tzinfo=UTC), None, {}, set(), [5, 4, 2, 3], 4),
        (0, 99, datetime(2021, 4, 5, 10, 3, 0, tzinfo=UTC), None, {}, set(), [5, 4, 3], 3),
        (0, 99, datetime(2021, 4, 5, 10, 4, 0, tzinfo=UTC), None, {}, set(), [5, 4], 2),
        (0, 99, datetime(2021, 4, 5, 10, 5, 0, tzinfo=UTC), None, {}, set(), [], 0),
        (0, 99, datetime(2021, 4, 5, 10, 2, 0, tzinfo=UTC), 1, {}, set(), [2, 3], 2),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_site_control_groups(
    extra_site_control_groups,
    start: int | None,
    limit: int | None,
    changed_after: datetime,
    fsa_id: int | None,
    scg_restrictions: dict[int, int],
    site_group_ids: set[int],
    expected_ids: list[int],
    expected_count: int,
):
    # This is a cache of known site_control_group_default values, keyed by the SiteControlGroup id
    #
    # If an ID isn't in here - it's because it doesn't have a default
    #
    # These values correspond to the SiteControlGroupDefault values in base_config.sql
    scg_default_import_limit: dict[int, Decimal] = {
        1: Decimal("10.10"),
        3: Decimal("20.20"),
    }

    # Rewrite the site control groups required_site_group_id - initially they are all NULL
    async with generate_async_session(extra_site_control_groups) as session:
        for scg_id, site_group_id in scg_restrictions.items():
            await session.execute(
                update(SiteControlGroup)
                .values(required_site_group_id=site_group_id)
                .where(SiteControlGroup.site_control_group_id == scg_id)
            )
        await session.commit()

    for include_defaults in [True, False]:
        async with generate_async_session(extra_site_control_groups) as session:
            actual_groups = await select_site_control_groups(
                session, start, changed_after, limit, fsa_id, site_group_ids, include_defaults=include_defaults
            )
            assert expected_ids == [e.site_control_group_id for e in actual_groups]
            assert_list_type(SiteControlGroup, actual_groups, len(expected_ids))

            actual_count = await count_site_control_groups(session, changed_after, site_group_ids, fsa_id)
            assert isinstance(actual_count, int)
            assert actual_count == expected_count

            if include_defaults:
                for g in actual_groups:
                    expected_import_default = scg_default_import_limit.get(g.site_control_group_id, None)
                    if expected_import_default is None:
                        assert g.site_control_group_default is None
                    else:
                        assert g.site_control_group_default is not None, (
                            f"SiteControlGroup ID: {g.site_control_group_id}"
                        )
                        assert g.site_control_group_default.import_limit_active_watts == expected_import_default, (
                            f"SiteControlGroup ID: {g.site_control_group_id}"
                        )

            else:
                for g in actual_groups:
                    with pytest.raises(InvalidRequestError):
                        assert g.site_control_group_default
                        g.site_control_group_default.created_time  # noqa: B018


@pytest.mark.anyio
async def test_count_site_control_groups_by_fsa_id(extra_site_control_groups):
    async with generate_async_session(extra_site_control_groups) as session:
        result = await count_site_control_groups_by_fsa_id(session)
        assert_dict_type(int, int, result, 2)
        assert result == {1: 3, 3: 1}


@pytest.mark.anyio
async def test_count_site_control_groups_by_fsa_id_with_nones(extra_site_control_groups):
    async with generate_async_session(extra_site_control_groups) as session:
        await session.execute(
            update(SiteControlGroup).values(fsa_id=None).where(SiteControlGroup.site_control_group_id.in_([1, 3]))
        )
        await session.commit()
    async with generate_async_session(extra_site_control_groups) as session:
        result = await count_site_control_groups_by_fsa_id(session)
        assert_dict_type(int, int, result, 2)
        assert result == {1: 1, 3: 1}


@pytest.mark.anyio
async def test_count_site_control_groups_by_fsa_id_empty_db(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        result = await count_site_control_groups_by_fsa_id(session)
        assert_dict_type(int, int, result, 0)


@pytest.mark.parametrize(
    "changed_after, expected_fsa_ids",
    [
        (datetime.min, [1, 3]),
        (datetime(2021, 4, 5, 10, 1, 0, tzinfo=UTC), [1, 3]),
        (datetime(2021, 4, 5, 10, 2, 0, tzinfo=UTC), [1, 3]),
        (datetime(2021, 4, 5, 10, 2, 0, tzinfo=UTC), [1, 3]),
        (datetime(2021, 4, 5, 10, 4, 0, tzinfo=UTC), [3]),
        (datetime(2021, 4, 5, 10, 6, 0, tzinfo=UTC), []),
    ],
)
@pytest.mark.anyio
async def test_select_site_control_group_fsa_ids(
    extra_site_control_groups,
    changed_after: datetime,
    expected_fsa_ids: list[int],
):
    async with generate_async_session(extra_site_control_groups) as session:
        actual_ids = await select_site_control_group_fsa_ids(session, changed_after)
        assert_list_type(int, actual_ids, len(expected_fsa_ids))
        assert set(expected_fsa_ids) == set(actual_ids)


@pytest.fixture
async def site_control_group_with_required_site_group(pg_base_config):
    """Adds a SiteControlGroup (id 6) whose required_site_group_id is set to site2's singleton group (id 4) -
    only site2 should be able to "see" this group"""
    async with generate_async_session(pg_base_config) as session:
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=606,
                site_control_group_id=6,
                primacy=99,
                fsa_id=None,
                display_id=None,
                required_site_group_id=4,
                changed_time=datetime(2021, 4, 5, 10, 6, 0, 500000, tzinfo=UTC),
            )
        )
        await session.commit()
    yield pg_base_config


@pytest.mark.parametrize(
    "site_group_ids, expected_visible",
    [
        (None, True),  # No site scope (eg admin) - always visible
        ({4}, True),  # has site_group 4
        ({1, 4, 99}, True),  # has site_group 4
        ({1, 2}, False),  # lacks site group 4
        (set(), False),  # lacks site group 4
        ({99, 1}, False),  # lacks site group 4
    ],
)
@pytest.mark.anyio
async def test_select_site_control_group_by_id_required_site_group_id_filtering(
    pg_base_config, site_group_ids: set[int] | None, expected_visible: bool
):
    async with generate_async_session(pg_base_config) as session:
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=101,
                optional_is_none=True,
                site_control_group_id=6,
                required_site_group_id=4,
            )
        )
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        result = await select_site_control_group_by_id(session, 6, site_group_ids=site_group_ids)
        if expected_visible:
            assert result is not None
            assert result.site_control_group_id == 6
        else:
            assert result is None
