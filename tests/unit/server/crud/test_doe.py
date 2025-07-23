from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import select, update

from envoy.admin.crud.doe import upsert_many_doe
from envoy.server.crud.doe import (
    count_active_does_include_deleted,
    count_does_at_timestamp,
    count_site_control_groups,
    select_active_does_include_deleted,
    select_doe_include_deleted,
    select_does_at_timestamp,
    select_site_control_group_by_id,
    select_site_control_group_fsa_ids,
    select_site_control_groups,
)
from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.manager.time import utc_now
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope as ArchiveDOE
from envoy.server.model.doe import DynamicOperatingEnvelope as DOE
from envoy.server.model.doe import SiteControlGroup
from envoy.server.model.site import Site

AEST = ZoneInfo("Australia/Brisbane")


def assert_doe_for_id(
    expected_doe_id: Optional[int],
    expected_site_id: Optional[int],
    expected_datetime: Optional[datetime],
    expected_tz: Optional[str],
    actual_doe: Optional[DOE],
    check_duration_seconds: bool = True,
):
    """Asserts the supplied doe matches the expected values for a doe with that id. These values are based
    purely on the data patterns in base_config.sql"""
    if expected_doe_id is None:
        assert actual_doe is None
    else:
        # This is just by convention
        if actual_doe.dynamic_operating_envelope_id in {18, 19, 20}:
            assert isinstance(actual_doe, ArchiveDOE)
        else:
            assert isinstance(actual_doe, DOE)

        assert actual_doe.dynamic_operating_envelope_id == expected_doe_id
        assert expected_site_id is None or actual_doe.site_id == expected_site_id
        assert actual_doe.site_control_group_id == 1
        if check_duration_seconds:
            assert actual_doe.duration_seconds == 10 * expected_doe_id + expected_doe_id
        assert actual_doe.import_limit_active_watts == Decimal(f"{expected_doe_id}.11")
        assert actual_doe.export_limit_watts == Decimal(f"-{expected_doe_id}.22")
        if expected_doe_id == 2:
            assert actual_doe.generation_limit_active_watts is None
            assert actual_doe.load_limit_active_watts is None
            assert actual_doe.set_point_percentage is None
            assert actual_doe.ramp_time_seconds is None
        else:
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

        if expected_tz:
            tz = ZoneInfo(expected_tz)
            assert actual_doe.start_time.tzname() == tz.tzname(
                actual_doe.start_time
            ), "Start time should be returned in local time"

            if expected_datetime:
                expected_in_local = datetime(
                    expected_datetime.year,
                    expected_datetime.month,
                    expected_datetime.day,
                    expected_datetime.hour,
                    expected_datetime.minute,
                    expected_datetime.second,
                    tzinfo=tz,
                )
                assert_datetime_equal(actual_doe.start_time, expected_in_local)
                assert actual_doe.start_time.tzname() == tz.tzname(
                    actual_doe.start_time
                ), "Start time should be returned in local time"
                assert_datetime_equal(actual_doe.created_time, datetime(2000, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc))


@pytest.mark.parametrize(
    "agg_id, site_id, doe_id, expected_dt",
    [
        (1, 1, 5, datetime(2023, 5, 7, 1, 0, 0)),
        (2, 3, 15, datetime(2023, 5, 7, 1, 5, 0)),
        (1, 1, 18, datetime(2023, 5, 7, 1, 0, 0)),  # Archive record
        (1, 1, 19, datetime(2023, 5, 7, 1, 5, 0)),  # Archive record
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
    site_id: Optional[int],
    doe_id: int,
    expected_dt: Optional[datetime],
):
    async with generate_async_session(pg_additional_does) as session:
        actual = await select_doe_include_deleted(session, agg_id, site_id, doe_id)
        if expected_dt is None:
            expected_id = None
        else:
            expected_id = doe_id
        assert_doe_for_id(expected_id, site_id, expected_dt, "Australia/Brisbane", actual, check_duration_seconds=False)


@pytest.mark.parametrize(
    "agg_id, site_id, doe_id, expected_dt",
    [
        (1, 1, 1, datetime(2022, 5, 6, 8, 2)),  # Adjusted for LA time
        (1, 1, 4, datetime(2022, 5, 7, 8, 2)),  # Adjusted for LA time
        (99, 99, 99, None),
    ],
)
@pytest.mark.anyio
async def test_select_doe_include_deleted_la_timezone(
    pg_la_timezone,
    agg_id: int,
    site_id: Optional[int],
    doe_id: int,
    expected_dt: Optional[datetime],
):
    async with generate_async_session(pg_la_timezone) as session:
        actual = await select_doe_include_deleted(session, agg_id, site_id, doe_id)
        if expected_dt is None:
            expected_id = None
        else:
            expected_id = doe_id
        assert_doe_for_id(
            expected_id, site_id, expected_dt, "America/Los_Angeles", actual, check_duration_seconds=False
        )


@pytest.mark.anyio
async def test_select_and_count_active_does_fails_none_site(pg_additional_does):
    """Tests out that passing a "None" value to the count/select functions raises an error"""

    now = datetime(2022, 11, 4, tzinfo=timezone.utc)
    after = datetime.min
    async with generate_async_session(pg_additional_does) as session:
        with pytest.raises(Exception):
            await select_active_does_include_deleted(session, 1, None, now, 0, after, 99)
        with pytest.raises(Exception):
            await count_active_does_include_deleted(session, 1, None, now, after)


@pytest.mark.parametrize(
    "expected_ids, expected_count, start, after, limit",
    [
        ([1, 2, 4, 18, 5, 9, 19, 6, 7, 8], 10, 0, datetime.min, 99),
        ([1], 10, 0, datetime.min, 1),
        ([4, 18, 5], 10, 2, datetime.min, 3),
        ([], 10, 0, datetime.min, 0),
        ([], 10, 99, datetime.min, 99),
        ([2, 4, 18, 5, 9, 19, 6, 7, 8], 9, 0, datetime(2022, 5, 6, 12, 22, 32, tzinfo=timezone.utc), 99),
        ([18, 5, 19, 6, 7, 8], 6, 0, datetime(2023, 5, 6, 11, 22, 32, tzinfo=timezone.utc), 99),
        ([5, 19], 6, 1, datetime(2023, 5, 6, 11, 22, 32, tzinfo=timezone.utc), 2),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_active_does_include_deleted_pagination(
    pg_additional_does, expected_ids: list[int], expected_count: int, start: int, after: datetime, limit: int
):
    """Tests out the basic pagination features"""
    now = datetime(1970, 1, 1, 0, 0, 0)  # This is sufficiently in this past to allow everything to pass
    site_control_group_id = 1

    async with generate_async_session(pg_additional_does) as session:
        existing_site = await select_single_site_with_site_id(session, 1, 1)
        does = await select_active_does_include_deleted(
            session, site_control_group_id, existing_site, now, start, after, limit
        )
        count = await count_active_does_include_deleted(session, site_control_group_id, existing_site, now, after)
        assert len(does) == len(expected_ids)
        assert count == expected_count
        for id, doe in zip(expected_ids, does):
            assert_doe_for_id(id, 1, None, None, doe, check_duration_seconds=False)


@pytest.mark.parametrize(
    "expected_ids, site_control_group_id, agg_id, site_id, now",
    [
        ([1, 2, 4, 18, 5, 9, 19, 6, 7, 8], 1, 1, 1, datetime.min),
        ([3, 20, 10, 11, 12, 13], 1, 1, 2, datetime.min),
        ([18, 5, 9, 19, 6, 7, 8], 1, 1, 1, datetime(2023, 5, 7, 0, 59, 59, tzinfo=AEST)),  # Before start
        ([18, 5, 9, 19, 6, 7, 8], 1, 1, 1, datetime(2023, 5, 7, 1, 4, 59, tzinfo=AEST)),  # Before end
        ([9, 19, 6, 7, 8], 1, 1, 1, datetime(2023, 5, 7, 1, 5, 0, tzinfo=AEST)),  # On expiry time
        ([18, 5, 9, 19, 6, 7, 8], 1, 1, 1, datetime(2023, 5, 7, 0, 59, 59, tzinfo=AEST)),  # Before start
        ([], 1, 1, 1, datetime(2045, 1, 1, 0, 0, 0, tzinfo=AEST)),  # Everything expired
        ([], 99, 1, 1, datetime.min),  # wrong site group id
    ],
)
@pytest.mark.anyio
async def test_select_and_count_active_does_include_deleted_filtered(
    pg_additional_does, site_control_group_id: int, expected_ids: list[int], agg_id: int, site_id: int, now: datetime
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_additional_does) as session:
        existing_site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=agg_id)

        does = await select_active_does_include_deleted(
            session, site_control_group_id, existing_site, now, 0, datetime.min, 99
        )
        count = await count_active_does_include_deleted(
            session, site_control_group_id, existing_site, now, datetime.min
        )
        assert isinstance(count, int)

        assert expected_ids == [d.dynamic_operating_envelope_id for d in does]
        assert len(does) == count

        for doe_id, doe in zip(expected_ids, does):
            assert_doe_for_id(doe_id, site_id, None, "Australia/Brisbane", doe, check_duration_seconds=False)


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
        session.add(generate_class_instance(SiteControlGroup, site_control_group_id=2))
        await session.flush()

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
        existing_site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=agg_id)

        does = await select_active_does_include_deleted(
            session, site_control_group_id, existing_site, now, 0, datetime.min, 99
        )
        count = await count_active_does_include_deleted(
            session, site_control_group_id, existing_site, now, datetime.min
        )
        assert isinstance(count, int)

        assert expected_ids == [d.dynamic_operating_envelope_id for d in does]
        assert len(does) == count

        for doe_id, doe in zip(expected_ids, does):
            assert doe.dynamic_operating_envelope_id == doe_id
            assert doe.site_control_group_id == site_control_group_id


@pytest.mark.parametrize(
    "expected_id_and_starts, agg_id, site_id",
    [
        (
            [(1, datetime(2022, 5, 6, 8, 2)), (2, datetime(2022, 5, 6, 10, 4)), (4, datetime(2022, 5, 7, 8, 2))],
            1,
            1,
        ),  # Adjusted for LA time
        ([(3, datetime(2022, 5, 6, 8, 2))], 1, 2),  # Adjusted for LA time
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_filters_la_time(
    pg_la_timezone, expected_id_and_starts: list[tuple[int, datetime]], agg_id: int, site_id: int
):
    """Builds on test_select_and_count_doe_filters with the la timezone"""
    now = datetime(1970, 1, 1, 0, 0, 0)  # This is sufficiently in this past to allow everything to pass
    site_control_group_id = 1
    async with generate_async_session(pg_la_timezone) as session:
        existing_site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=agg_id)
        does = await select_active_does_include_deleted(
            session, site_control_group_id, existing_site, now, 0, datetime.min, 99
        )
        count = await count_active_does_include_deleted(
            session, site_control_group_id, existing_site, now, datetime.min
        )
        assert isinstance(count, int)
        assert len(does) == len(expected_id_and_starts)
        assert len(does) == count
        for (id, expected_datetime), doe in zip(expected_id_and_starts, does):
            assert_doe_for_id(id, site_id, expected_datetime, "America/Los_Angeles", doe)


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
        site_id=1,
        site_control_group_id=1,
        site=None,
        site_control_group=None,
    )
    async with generate_async_session(pg_base_config) as session:
        site = (await session.execute(select(Site).where(Site.site_id == 1))).scalar_one()
        site_control_group = (
            await session.execute(select(SiteControlGroup).where(SiteControlGroup.site_control_group_id == 1))
        ).scalar_one()

        cloned_doe = clone_class_instance(doe_to_delete)
        cloned_doe.site = site
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
        site_id=1,
        site_control_group_id=1,
        calculation_log_id=None,
    )
    doe_to_insert = generate_class_instance(
        DOE,
        seed=303,
        start_time=start_time_to_delete - timedelta(seconds=1),
        duration_seconds=duration_seconds,
        end_time=end_time_to_delete - timedelta(seconds=1),
        site_id=1,
        site_control_group_id=1,
        calculation_log_id=None,
    )
    async with generate_async_session(pg_base_config) as session:
        await upsert_many_doe(session, [doe_to_replace, doe_to_insert], now)
        await session.commit()

    # Now refetch everything using select_active_does_include_deleted - This will include three DOEs consisting of:
    # the archived doe_to_delete
    # the active doe_to_replace
    # the active doe_to_insert
    async with generate_async_session(pg_base_config) as session:
        results = await select_active_does_include_deleted(
            session, 1, Site(site_id=1, timezone_id="Australia/Brisbane"), now, 0, datetime.min, 99
        )
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
    "expected_id_and_starts, timestamp, site_control_group_id, agg_id, site_id",
    [
        (
            [(5, datetime(2023, 5, 7, 1, 0, 0))],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            1,
        ),  # For Agg 1 / Site 1 at timestamp
        (
            [(10, datetime(2023, 5, 7, 1, 0, 0)), (5, datetime(2023, 5, 7, 1, 0, 0))],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            None,
        ),  # For Agg 1 / ANY Site at timestamp
        (
            [(5, datetime(2023, 5, 7, 1, 0, 0)), (9, datetime(2023, 5, 7, 1, 0, 1))],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            1,
        ),  # For Agg 1 / ANY Site at timestamp (that overlaps multiple DOEs)
        (
            [
                (10, datetime(2023, 5, 7, 1, 0, 0)),
                (5, datetime(2023, 5, 7, 1, 0, 0)),
                (9, datetime(2023, 5, 7, 1, 0, 1)),
            ],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            None,
        ),  # For Agg 1 / ANY Site at timestamp (that overlaps multiple DOEs)
        (
            [(5, datetime(2023, 5, 7, 1, 0, 0)), (9, datetime(2023, 5, 7, 1, 0, 1))],
            datetime(2023, 5, 7, 1, 3, 22, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            1,
        ),
        (
            [
                (10, datetime(2023, 5, 7, 1, 0, 0)),
                (5, datetime(2023, 5, 7, 1, 0, 0)),
                (9, datetime(2023, 5, 7, 1, 0, 1)),
            ],
            datetime(2023, 5, 7, 1, 3, 22, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            None,
        ),
        (
            [(9, datetime(2023, 5, 7, 1, 0, 1)), (6, datetime(2023, 5, 7, 1, 5, 0))],
            datetime(2023, 5, 7, 1, 5, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            1,
        ),
        (
            [(7, datetime(2023, 5, 7, 1, 10, 0))],
            datetime(2023, 5, 7, 1, 10, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            1,
        ),
        (
            [(14, datetime(2023, 5, 7, 1, 0, 0))],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            2,
            3,
        ),  # For agg 2
        (
            [],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            99,
            1,
        ),  # Bad Agg ID
        (
            [],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            2,
            1,
        ),  # Agg ID can't access another agg's sites
        (
            [],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            2,
            0,
        ),  # Zero site ID
        (
            [],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            1,
            99,
        ),  # Missing site ID
        (
            [],
            datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            2,
            1,
            1,
        ),  # Wrong site control id
        # Throw the timestamp timezone off
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")), 1, 1, None),
        ([], datetime(2023, 5, 7, 1, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")), 1, 1, 1),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_for_timestamp_filters(
    pg_additional_does,
    expected_id_and_starts: list[tuple[int, datetime]],
    timestamp: datetime,
    site_control_group_id: int,
    agg_id: int,
    site_id: Optional[int],
):
    """Tests out the basic filters features and validates the associated count function too"""
    async with generate_async_session(pg_additional_does) as session:
        does = await select_does_at_timestamp(
            session, site_control_group_id, agg_id, site_id, timestamp, 0, datetime.min, 99
        )
        count = await count_does_at_timestamp(session, site_control_group_id, agg_id, site_id, timestamp, datetime.min)
        assert isinstance(count, int)
        assert len(does) == len(expected_id_and_starts)
        assert len(does) == count
        for (id, expected_datetime), doe in zip(expected_id_and_starts, does):
            assert_doe_for_id(id, site_id, expected_datetime, "Australia/Brisbane", doe, check_duration_seconds=False)


@pytest.mark.parametrize(
    "expected_ids, timestamp, start, after, limit",
    [
        # Start
        ([5, 9], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 0, datetime.min, 99),
        ([9], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 1, datetime.min, 99),
        ([], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 2, datetime.min, 99),
        # Limit
        ([5], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 0, datetime.min, 1),
        ([], datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")), 0, datetime.min, 0),
        # After
        (
            [5, 9],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            0,
            datetime(2023, 2, 3, 11, 22, 32, tzinfo=timezone.utc),
            99,
        ),
        (
            [5],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            0,
            datetime(2023, 2, 3, 11, 22, 34, tzinfo=timezone.utc),
            99,
        ),
        (
            [],
            datetime(2023, 5, 7, 1, 0, 1, tzinfo=ZoneInfo("Australia/Brisbane")),
            0,
            datetime(2023, 5, 6, 11, 22, 34, tzinfo=timezone.utc),
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
        does = await select_does_at_timestamp(session, 1, 1, 1, timestamp, start, after, limit)
        assert len(does) == len(expected_ids)
        for id, doe in zip(expected_ids, does):
            assert_doe_for_id(id, 1, None, None, doe, check_duration_seconds=False)


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
                fsa_id=1,
                changed_time=datetime(2021, 4, 5, 10, 2, 0, 500000, tzinfo=timezone.utc),
            )
        )
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=202,
                primacy=1,
                site_control_group_id=3,
                fsa_id=3,
                changed_time=datetime(2021, 4, 5, 10, 3, 0, 500000, tzinfo=timezone.utc),
            )
        )
        session.add(
            generate_class_instance(
                SiteControlGroup,
                seed=303,
                primacy=1,
                site_control_group_id=4,
                fsa_id=1,
                changed_time=datetime(2021, 4, 5, 10, 4, 0, 500000, tzinfo=timezone.utc),
            )
        )
        await session.commit()
    yield pg_base_config


@pytest.mark.parametrize(
    "site_control_group_id, expected_primacy",
    [(1, 0), (3, 1), (99, None), (None, None)],
)
@pytest.mark.anyio
async def test_select_site_control_group_by_id(
    extra_site_control_groups, site_control_group_id: int, expected_primacy: Optional[int]
):
    """Tests that select_site_control_group_by_code works with a variety of success/failure cases"""

    async with generate_async_session(extra_site_control_groups) as session:
        result = await select_site_control_group_by_id(session, site_control_group_id)

        if expected_primacy is None:
            assert result is None
        else:
            assert isinstance(result, SiteControlGroup)
            assert result.primacy == expected_primacy
            assert result.site_control_group_id == site_control_group_id


@pytest.mark.parametrize(
    "start, limit, changed_after, fsa_id, expected_ids, expected_count",
    [
        (0, 99, datetime.min, None, [1, 4, 3, 2], 4),
        (0, 99, datetime.min, 1, [1, 4, 2], 3),
        (0, 99, datetime.min, 2, [], 0),
        (0, 99, datetime.min, 3, [3], 1),
        (1, 2, datetime.min, None, [4, 3], 4),
        (1, 1, datetime.min, 1, [4], 3),
        (99, 99, datetime.min, None, [], 4),
        (0, 99, datetime(2021, 4, 5, 10, 1, 0, tzinfo=timezone.utc), None, [1, 4, 3, 2], 4),
        (3, 99, datetime(2021, 4, 5, 10, 1, 0, tzinfo=timezone.utc), None, [2], 4),
        (0, 99, datetime(2021, 4, 5, 10, 2, 0, tzinfo=timezone.utc), None, [4, 3, 2], 3),
        (0, 99, datetime(2021, 4, 5, 10, 3, 0, tzinfo=timezone.utc), None, [4, 3], 2),
        (0, 99, datetime(2021, 4, 5, 10, 4, 0, tzinfo=timezone.utc), None, [4], 1),
        (0, 99, datetime(2021, 4, 5, 10, 5, 0, tzinfo=timezone.utc), None, [], 0),
        (0, 99, datetime(2021, 4, 5, 10, 2, 0, tzinfo=timezone.utc), 1, [4, 2], 2),
    ],
)
@pytest.mark.anyio
async def test_select_and_count_site_control_groups(
    extra_site_control_groups,
    start: Optional[int],
    limit: Optional[int],
    changed_after: datetime,
    fsa_id: Optional[int],
    expected_ids: list[int],
    expected_count: int,
):
    async with generate_async_session(extra_site_control_groups) as session:
        actual_groups = await select_site_control_groups(session, start, changed_after, limit, fsa_id)
        assert expected_ids == [e.site_control_group_id for e in actual_groups]
        assert_list_type(SiteControlGroup, actual_groups, len(expected_ids))

        actual_count = await count_site_control_groups(session, changed_after, fsa_id)
        assert isinstance(actual_count, int)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "changed_after, expected_fsa_ids",
    [
        (datetime.min, [1, 3]),
        (datetime(2021, 4, 5, 10, 1, 0, tzinfo=timezone.utc), [1, 3]),
        (datetime(2021, 4, 5, 10, 2, 0, tzinfo=timezone.utc), [1, 3]),
        (datetime(2021, 4, 5, 10, 2, 0, tzinfo=timezone.utc), [1, 3]),
        (datetime(2021, 4, 5, 10, 4, 0, tzinfo=timezone.utc), [1]),
        (datetime(2021, 4, 5, 10, 6, 0, tzinfo=timezone.utc), []),
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
