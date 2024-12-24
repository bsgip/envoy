from datetime import datetime, timedelta, timezone

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session

from envoy.admin.crud.archive import (
    count_archive_does_for_period,
    count_archive_rates_for_period,
    count_archive_sites_for_period,
    select_archive_does_for_period,
    select_archive_rates_for_period,
    select_archive_sites_for_period,
)
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate

# Arbitrary datetimes indicating the range of times where we have archived records for. Will constitute a few
# hours of range
DT1 = datetime(2022, 5, 6, 7, 8, 9, 500000, tzinfo=timezone.utc)
DT2 = DT1 + timedelta(hours=1.53)
DT3 = DT2 + timedelta(hours=8.42)


async def populate_archive_with_type(pg_base_config, t: type):
    async with generate_async_session(pg_base_config) as session:

        # Archive 1 sits at DT1 for both archive times and delete times
        session.add(generate_class_instance(t, seed=1001, archive_id=1, archive_time=DT1, deleted_time=DT1))

        # Archive 2 sits at DT1 for deleted time but archive time is out of range
        session.add(
            generate_class_instance(t, seed=2002, archive_id=2, archive_time=DT1 - timedelta(hours=1), deleted_time=DT1)
        )

        # Archive 3 sits at DT1 for archive time but deleted time is out of range
        session.add(
            generate_class_instance(t, seed=3003, archive_id=3, archive_time=DT1, deleted_time=DT1 - timedelta(hours=1))
        )

        # Archive 4 sits out of range (before)
        session.add(
            generate_class_instance(
                t,
                seed=4004,
                archive_id=4,
                archive_time=DT1 - timedelta(hours=1),
                deleted_time=DT1 - timedelta(hours=1),
            )
        )

        # Archive 5/6 sits out of range (after)
        session.add(generate_class_instance(t, seed=5005, archive_id=5, archive_time=DT3, deleted_time=DT3))
        session.add(
            generate_class_instance(
                t,
                seed=6006,
                archive_id=6,
                archive_time=DT3 + timedelta(hours=1),
                deleted_time=DT3 + timedelta(hours=1),
            )
        )

        # Archive 7 sits at DT2 for both archive times and delete times
        session.add(generate_class_instance(t, seed=7007, archive_id=7, archive_time=DT2, deleted_time=DT2))

        # Archive 8 sits just before DT2 for both archive times and delete times
        session.add(
            generate_class_instance(
                t,
                seed=8008,
                archive_id=8,
                archive_time=DT2 - timedelta(seconds=1),
                deleted_time=DT2 - timedelta(seconds=1),
            )
        )

        # Archive 9 sits just after DT2 for both archive times and delete times
        session.add(
            generate_class_instance(
                t,
                seed=9009,
                archive_id=9,
                archive_time=DT2 + timedelta(seconds=1),
                deleted_time=DT2 + timedelta(seconds=1),
            )
        )

        # Archive 10 sits on DT1 and isn't deleted
        session.add(
            generate_class_instance(
                t,
                seed=1010,
                archive_id=10,
                archive_time=DT1,
                deleted_time=None,
            )
        )

        # Archive 11 sits before DT1 and isn't deleted
        session.add(
            generate_class_instance(
                t,
                seed=1111,
                archive_id=11,
                archive_time=DT1 - timedelta(seconds=1),
                deleted_time=None,
            )
        )

        # Archive 12 sits after DT1 and isn't deleted
        session.add(
            generate_class_instance(
                t,
                seed=1212,
                archive_id=12,
                archive_time=DT1 + timedelta(seconds=1),
                deleted_time=None,
            )
        )
        await session.commit()


TEST_CASES = [
    (0, 999, DT1, DT3, False, [1, 3, 7, 8, 9, 10, 12], 7),  # Get everything for archives
    (0, 999, DT1, DT3, True, [1, 2, 7, 8, 9], 5),  # Get everything for deletes
    (0, 999, DT1, DT2, False, [1, 3, 8, 10, 12], 5),  # Get everything up to DT2 for archives
    (0, 999, DT1, DT2, True, [1, 2, 8], 3),  # Get everything up to DT2 for deleted
    (1, 2, DT1, DT3, False, [3, 7], 7),  # Archive pagination
    (999, 999, DT1, DT3, False, [], 7),  # Archive pagination
    (1, 2, DT1, DT3, True, [2, 7], 5),  # deletes pagination
    (999, 999, DT1, DT3, True, [], 5),  # deletes pagination
]


@pytest.mark.parametrize(
    "start, limit, period_start, period_end, only_deletes, expected_archive_ids, expected_count", TEST_CASES
)
@pytest.mark.anyio
async def test_archive_sites_for_period(
    pg_base_config,
    start: int,
    limit: int,
    period_start: datetime,
    period_end: datetime,
    only_deletes: bool,
    expected_archive_ids: list[int],
    expected_count: int,
):
    """Tests select_archive_sites_for_period and count_archive_sites_for_period work together and generate expected
    results"""

    # before loading the archive - nothing should be returned
    async with generate_async_session(pg_base_config) as session:
        sites = await select_archive_sites_for_period(session, start, limit, period_start, period_end, only_deletes)
        count = await count_archive_sites_for_period(session, period_start, period_end, only_deletes)
        assert sites == []
        assert count == 0

    await populate_archive_with_type(pg_base_config, ArchiveSite)

    async with generate_async_session(pg_base_config) as session:
        sites = await select_archive_sites_for_period(session, start, limit, period_start, period_end, only_deletes)
        assert_list_type(ArchiveSite, sites, len(expected_archive_ids))
        assert expected_archive_ids == [s.archive_id for s in sites]

        count = await count_archive_sites_for_period(session, period_start, period_end, only_deletes)
        assert count == expected_count


@pytest.mark.parametrize(
    "start, limit, period_start, period_end, only_deletes, expected_archive_ids, expected_count", TEST_CASES
)
@pytest.mark.anyio
@pytest.mark.anyio
async def test_archive_does_for_period(
    pg_base_config,
    start: int,
    limit: int,
    period_start: datetime,
    period_end: datetime,
    only_deletes: bool,
    expected_archive_ids: list[int],
    expected_count: int,
):
    """Tests select_archive_does_for_period and count_archive_does_for_period work together and generate expected
    results"""

    # before loading the archive - nothing should be returned
    async with generate_async_session(pg_base_config) as session:
        does = await select_archive_does_for_period(session, start, limit, period_start, period_end, only_deletes)
        count = await count_archive_does_for_period(session, period_start, period_end, only_deletes)
        assert does == []
        assert count == 0

    await populate_archive_with_type(pg_base_config, ArchiveDynamicOperatingEnvelope)

    async with generate_async_session(pg_base_config) as session:
        does = await select_archive_does_for_period(session, start, limit, period_start, period_end, only_deletes)
        assert_list_type(ArchiveDynamicOperatingEnvelope, does, len(expected_archive_ids))
        assert expected_archive_ids == [d.archive_id for d in does]

        count = await count_archive_does_for_period(session, period_start, period_end, only_deletes)
        assert count == expected_count


@pytest.mark.parametrize(
    "start, limit, period_start, period_end, only_deletes, expected_archive_ids, expected_count", TEST_CASES
)
@pytest.mark.anyio
@pytest.mark.anyio
async def test_archive_rates_for_period(
    pg_base_config,
    start: int,
    limit: int,
    period_start: datetime,
    period_end: datetime,
    only_deletes: bool,
    expected_archive_ids: list[int],
    expected_count: int,
):
    """Tests select_archive_rates_for_period and count_archive_rates_for_period work together and generate expected
    results"""

    # before loading the archive - nothing should be returned
    async with generate_async_session(pg_base_config) as session:
        rates = await select_archive_rates_for_period(session, start, limit, period_start, period_end, only_deletes)
        count = await count_archive_rates_for_period(session, period_start, period_end, only_deletes)
        assert rates == []
        assert count == 0

    await populate_archive_with_type(pg_base_config, ArchiveTariffGeneratedRate)

    async with generate_async_session(pg_base_config) as session:
        rates = await select_archive_rates_for_period(session, start, limit, period_start, period_end, only_deletes)
        assert_list_type(ArchiveTariffGeneratedRate, rates, len(expected_archive_ids))
        assert expected_archive_ids == [r.archive_id for r in rates]

        count = await count_archive_rates_for_period(session, period_start, period_end, only_deletes)
        assert count == expected_count
