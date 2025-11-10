from datetime import datetime, timezone
from itertools import product
from typing import Any, Optional

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.model.archive.base import ARCHIVE_BASE_COLUMNS
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from tests.unit.server.model.archive.test_archive_models import find_paired_archive_classes


async def fetch_all_values_as_tuples(
    session: AsyncSession, t: type, ignore_columns: Optional[set[str]] = None
) -> list[tuple]:
    """Fetches all rows from a table as a list of tuples"""

    if ignore_columns is None:
        ignore_columns = set()

    return (await session.execute(select(*[c for c in t.__table__.columns if c.name not in ignore_columns]))).all()


async def fetch_single_column(session: AsyncSession, t: type, column_name: str) -> list[Any]:
    """Fetches all rows from a table as a list of that value"""
    tuple_wrapped = (await session.execute(select(*[c for c in t.__table__.columns if c.name == column_name]))).all()
    return [v[0] for v in tuple_wrapped]


@pytest.mark.parametrize(
    "original_type, archive_type",
    find_paired_archive_classes(),
)
@pytest.mark.anyio
async def test_copy_rows_into_archive_no_matches(pg_base_config, original_type: type, archive_type: type):
    """Tests the copy into archive function when the where clause matches nothing (i.e. - it should do nothing)"""
    async with generate_async_session(pg_base_config) as session:
        await copy_rows_into_archive(session, original_type, archive_type, lambda q: q.where(False))
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Ensure nothing is copied
        assert (await session.execute(select(func.count()).select_from(archive_type))).scalar_one() == 0


@pytest.mark.parametrize(
    "original_type, archive_type, commit",
    [(ot, at, c) for (ot, at), c in product(find_paired_archive_classes(), [True, False])],
)
@pytest.mark.anyio
async def test_copy_rows_into_archive_all_matches(
    pg_base_config, original_type: type, archive_type: type, commit: bool
):
    """Tests the copy into archive function when the where clause matches EVERYTHING (i.e. - it should copy all rows).

    Also double checks the copying is tied into the parent transaction"""
    async with generate_async_session(pg_base_config) as session:
        original_count_before = (await session.execute(select(func.count()).select_from(original_type))).scalar_one()
        assert original_count_before > 0
        original_values = await fetch_all_values_as_tuples(session, original_type)

        await copy_rows_into_archive(session, original_type, archive_type, lambda q: q.where(True))

        if commit:
            await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Ensure everything is copied
        archive_count = (await session.execute(select(func.count()).select_from(archive_type))).scalar_one()

        assert original_values == await fetch_all_values_as_tuples(
            session, original_type
        ), "Original table should be unchanged"

        if commit:
            assert archive_count == original_count_before
            assert original_values == await fetch_all_values_as_tuples(
                session, archive_type, ignore_columns=ARCHIVE_BASE_COLUMNS
            ), "Columns archived should be a straight copy from original table (ignoring the archive columns)"

            # Validate the archive specific metadata
            deleted_time_vals = await fetch_single_column(session, archive_type, "deleted_time")
            assert all((v is None for v in deleted_time_vals)), "Nothing should be marked as deleted"
            for archive_time in await fetch_single_column(session, archive_type, "archive_time"):
                assert_nowish(archive_time)
            assert all((v is None for v in deleted_time_vals))
        else:
            assert archive_count == 0


@pytest.mark.parametrize(
    "original_type, archive_type",
    find_paired_archive_classes(),
)
@pytest.mark.anyio
async def test_copy_rows_into_archive_multiple_times(pg_base_config, original_type: type, archive_type: type):
    """Tests the copy into archive function can repeatedly add to the archive without issue"""
    async with generate_async_session(pg_base_config) as session:
        original_count_before = (await session.execute(select(func.count()).select_from(original_type))).scalar_one()
        original_values = await fetch_all_values_as_tuples(session, original_type)

    loop_count = 3
    for _ in range(loop_count):
        async with generate_async_session(pg_base_config) as session:
            await copy_rows_into_archive(session, original_type, archive_type, lambda q: q.where(True))
            await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Ensure everything is copied, multiple times
        archive_count = (await session.execute(select(func.count()).select_from(archive_type))).scalar_one()
        assert archive_count == (original_count_before * loop_count)

        # We should be archiving the same values over and over
        archive_values = await fetch_all_values_as_tuples(session, archive_type, ignore_columns=ARCHIVE_BASE_COLUMNS)
        assert original_values * loop_count == archive_values

        # Validate the archive specific metadata
        deleted_time_vals = await fetch_single_column(session, archive_type, "deleted_time")
        assert all((v is None for v in deleted_time_vals)), "Nothing should be marked as deleted"
        for archive_time in await fetch_single_column(session, archive_type, "archive_time"):
            assert_nowish(archive_time)


@pytest.mark.anyio
async def test_copy_rows_into_archive_complex_filter(pg_base_config):
    """Sanity check on the where_filter - specifically that it allows us to chain some complex logic"""
    async with generate_async_session(pg_base_config) as session:
        # This will match Site 1 and Site 3
        await copy_rows_into_archive(
            session,
            Site,
            ArchiveSite,
            lambda q: q.where(
                or_(Site.site_id == 3, Site.changed_time == datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc))
            ),
        )
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Ensure everything is copied
        assert (
            await session.execute(select(func.count()).select_from(ArchiveSite))
        ).scalar_one() == 2, "Only 2 sites should've matched and been brought across"

        # Validate the archive values (partially)
        assert (await fetch_single_column(session, ArchiveSite, "site_id")) == [1, 3]
        assert (await fetch_single_column(session, ArchiveSite, "lfdi")) == [
            "1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a",
            "3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c",
        ]
        assert (await fetch_single_column(session, ArchiveSite, "sfdi")) == [1111, 3333]

        # Validate the archive specific metadata
        deleted_time_vals = await fetch_single_column(session, ArchiveSite, "deleted_time")
        assert all((v is None for v in deleted_time_vals)), "Nothing should be marked as deleted"
        for archive_time in await fetch_single_column(session, ArchiveSite, "archive_time"):
            assert_nowish(archive_time)


@pytest.mark.parametrize(
    "original_type, archive_type",
    find_paired_archive_classes(),
)
@pytest.mark.anyio
async def test_delete_rows_into_archive_no_matches(pg_base_config, original_type: type, archive_type: type):
    """Check that delete_rows_into_archive does nothing if the where clause matches nothing"""

    deleted_time = datetime(2021, 5, 6, 7, 8, 9, 1234, tzinfo=timezone.utc)

    async with generate_async_session(pg_base_config) as session:
        count_before = (await session.execute(select(func.count()).select_from(original_type))).scalar_one()
        assert count_before > 0, "This isn't testing anything if this fails"
        original_values = await fetch_all_values_as_tuples(session, original_type)

        await delete_rows_into_archive(session, original_type, archive_type, deleted_time, lambda q: q.where(False))
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Ensure nothing is copied / deleted
        assert (await session.execute(select(func.count()).select_from(archive_type))).scalar_one() == 0
        assert count_before == (await session.execute(select(func.count()).select_from(original_type))).scalar_one()
        assert original_values == (await fetch_all_values_as_tuples(session, original_type)), "No changes"


@pytest.mark.parametrize(
    "original_type, archive_type, commit",
    [
        (ot, at, c)
        for (ot, at), c in product(
            (
                (ot, at)
                for ot, at in find_paired_archive_classes()
                if ot not in {Site, Tariff, SiteReadingType, SiteControlGroup}
            ),
            [True, False],
        )
    ],
)
@pytest.mark.anyio
async def test_delete_rows_into_archive_all_matches(
    pg_base_config, original_type: type, archive_type: type, commit: bool
):
    """Check that delete_rows_into_archive can delete everything if the where clause matches everything

    NOTE - this test won't cover types that have FK dependencies"""

    deleted_time = datetime(2021, 5, 6, 7, 8, 9, 1234, tzinfo=timezone.utc)

    async with generate_async_session(pg_base_config) as session:
        original_count_before = (await session.execute(select(func.count()).select_from(original_type))).scalar_one()
        assert original_count_before > 0, "This isn't testing anything if this fails"
        original_values = await fetch_all_values_as_tuples(session, original_type)

        await delete_rows_into_archive(session, original_type, archive_type, deleted_time, lambda q: q.where(True))

        if commit:
            await session.commit()

    async with generate_async_session(pg_base_config) as session:
        original_count_after = (await session.execute(select(func.count()).select_from(original_type))).scalar_one()
        archive_count_after = (await session.execute(select(func.count()).select_from(archive_type))).scalar_one()

        if commit:
            assert original_count_after == 0
            assert archive_count_after == original_count_before
            assert original_values == await fetch_all_values_as_tuples(
                session, archive_type, ignore_columns=ARCHIVE_BASE_COLUMNS
            )

            # Validate the archive specific metadata
            deleted_time_vals = await fetch_single_column(session, ArchiveSite, "deleted_time")
            assert all((v == deleted_time for v in deleted_time_vals)), "Should match supplied datetime"
            for archive_time in await fetch_single_column(session, ArchiveSite, "archive_time"):
                assert_nowish(archive_time)
        else:
            assert original_count_after == original_count_before
            assert archive_count_after == 0
            assert original_values == await fetch_all_values_as_tuples(session, original_type)


@pytest.mark.anyio
async def test_delete_rows_into_archive_complex_filter(pg_base_config):
    """Check that delete_rows_into_archive can handle a complex filter.

    The filter will delete The first and last TariffGeneratedRate"""

    deleted_time = datetime(2022, 1, 2, 3, 8, 9, 1234, tzinfo=timezone.utc)

    async with generate_async_session(pg_base_config) as session:
        original_count_before = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRate))
        ).scalar_one()
        original_values = await fetch_all_values_as_tuples(session, TariffGeneratedRate)

        await delete_rows_into_archive(
            session,
            TariffGeneratedRate,
            ArchiveTariffGeneratedRate,
            deleted_time,
            lambda q: q.where(
                or_(TariffGeneratedRate.tariff_generated_rate_id == 1, TariffGeneratedRate.duration_seconds == 14)
            ),
        )

        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        original_count_after = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRate))
        ).scalar_one()
        archive_count_after = (
            await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))
        ).scalar_one()

        assert original_count_after == (original_count_before - 2), "Only two rates should've been archived"
        assert archive_count_after == 2, "Only two rates should've been archived"
        original_values_after = await fetch_all_values_as_tuples(session, TariffGeneratedRate)
        archive_values_after = await fetch_all_values_as_tuples(
            session, ArchiveTariffGeneratedRate, ignore_columns=ARCHIVE_BASE_COLUMNS
        )

        assert original_values[1:3] == original_values_after, "The second and third rates should be left in place"
        assert [original_values[0], original_values[3]] == archive_values_after, "First and fourth rates should archive"

        # Validate the archive specific metadata
        deleted_time_vals = await fetch_single_column(session, ArchiveSite, "deleted_time")
        assert all((v == deleted_time for v in deleted_time_vals)), "Should match supplied datetime"
        for archive_time in await fetch_single_column(session, ArchiveSite, "archive_time"):
            assert_nowish(archive_time)


@pytest.mark.anyio
async def test_delete_rows_into_archive_cascade_deletes(pg_base_config):
    """Check we can us delete_rows_into_archive to cascade deletes over multiple queries."""

    deleted_time = datetime(2021, 9, 2, 3, 8, 9, 12345, tzinfo=timezone.utc)

    async with generate_async_session(pg_base_config) as session:
        # We can't do joins via this method, instead we hardcode all the SiteReadingType IDs that belong to site 1
        await delete_rows_into_archive(
            session,
            SiteReading,
            ArchiveSiteReading,
            deleted_time,
            lambda q: q.where(SiteReading.site_reading_type_id.in_([1, 2, 3])),
        )

        await delete_rows_into_archive(
            session,
            SiteReadingType,
            ArchiveSiteReadingType,
            deleted_time,
            lambda q: q.where(SiteReadingType.site_id == 1),
        )

        await delete_rows_into_archive(
            session,
            DynamicOperatingEnvelope,
            ArchiveDynamicOperatingEnvelope,
            deleted_time,
            lambda q: q.where(DynamicOperatingEnvelope.site_id == 1),
        )

        await delete_rows_into_archive(
            session,
            TariffGeneratedRate,
            ArchiveTariffGeneratedRate,
            deleted_time,
            lambda q: q.where(TariffGeneratedRate.site_id == 1),
        )

        await delete_rows_into_archive(
            session,
            Site,
            ArchiveSite,
            deleted_time,
            lambda q: q.where(Site.site_id == 1),
        )

        await session.commit()

    # Now do some top level validation
    async with generate_async_session(pg_base_config) as session:
        assert 5 == (await session.execute(select(func.count()).select_from(Site))).scalar_one()
        assert 1 == (await session.execute(select(func.count()).select_from(ArchiveSite))).scalar_one()

        assert 1 == (await session.execute(select(func.count()).select_from(TariffGeneratedRate))).scalar_one()
        assert 3 == (await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))).scalar_one()

        assert 1 == (await session.execute(select(func.count()).select_from(DynamicOperatingEnvelope))).scalar_one()
        assert (
            3 == (await session.execute(select(func.count()).select_from(ArchiveDynamicOperatingEnvelope))).scalar_one()
        )

        assert 1 == (await session.execute(select(func.count()).select_from(SiteReadingType))).scalar_one()
        assert 4 == (await session.execute(select(func.count()).select_from(ArchiveSiteReadingType))).scalar_one()

        assert 1 == (await session.execute(select(func.count()).select_from(SiteReading))).scalar_one()
        assert 3 == (await session.execute(select(func.count()).select_from(ArchiveSiteReading))).scalar_one()


@pytest.mark.anyio
async def test_delete_after_copy(pg_base_config):
    """Check that delete_rows_into_archive can run after copy_rows_into_archive"""

    deleted_time = datetime(2024, 1, 2, 3, 8, 9, 1234, tzinfo=timezone.utc)

    async with generate_async_session(pg_base_config) as session:
        original_count_before = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRate))
        ).scalar_one()
        original_values = await fetch_all_values_as_tuples(session, TariffGeneratedRate)

        await copy_rows_into_archive(
            session,
            TariffGeneratedRate,
            ArchiveTariffGeneratedRate,
            lambda q: q.where(TariffGeneratedRate.tariff_generated_rate_id == 1),
        )

        await delete_rows_into_archive(
            session,
            TariffGeneratedRate,
            ArchiveTariffGeneratedRate,
            deleted_time,
            lambda q: q.where(TariffGeneratedRate.tariff_generated_rate_id == 1),
        )

        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        original_count_after = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRate))
        ).scalar_one()
        archive_count_after = (
            await session.execute(select(func.count()).select_from(ArchiveTariffGeneratedRate))
        ).scalar_one()

        assert original_count_after == (original_count_before - 1), "Only one rate was deleted"
        assert archive_count_after == 2, "But it was archived twice. Once for copy, Once for delete"
        archive_values_after = await fetch_all_values_as_tuples(
            session, ArchiveTariffGeneratedRate, ignore_columns=ARCHIVE_BASE_COLUMNS
        )

        assert original_values[0:1] * 2 == archive_values_after, "The same row was archived twice"

        # Validate the archive specific metadata
        deleted_time_vals = await fetch_single_column(session, ArchiveTariffGeneratedRate, "deleted_time")
        assert [None, deleted_time] == deleted_time_vals
        for archive_time in await fetch_single_column(session, ArchiveTariffGeneratedRate, "archive_time"):
            assert_nowish(archive_time)
