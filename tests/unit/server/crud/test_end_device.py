from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from typing import Callable, Optional, Union

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import clone_class_instance, generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.types import DeviceCategory
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.end_device import (
    delete_site_for_aggregator,
    get_virtual_site_for_aggregator,
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_first_site_under_aggregator,
    select_single_site_with_lfdi,
    select_single_site_with_sfdi,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.manager.time import utc_now
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import (
    ArchiveSite,
    ArchiveSiteDER,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.archive.subscription import ArchiveSubscription, ArchiveSubscriptionCondition
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.base import Base
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionCondition
from envoy.server.model.tariff import TariffGeneratedRate


@pytest.mark.parametrize(
    "aggregator_id, changed_after, expected_count",
    [
        # Test the basic config is there and accessible
        (1, datetime.min, 3),
        (2, datetime.min, 1),
        (3, datetime.min, 0),
        # try with after filter being set
        (1, datetime(2022, 2, 3, 0, 0, 0, tzinfo=timezone.utc), 3),
        (1, datetime(2022, 2, 3, 5, 0, 0, tzinfo=timezone.utc), 2),
        (1, datetime(2022, 2, 3, 8, 0, 0, tzinfo=timezone.utc), 1),
        (1, datetime(2022, 2, 3, 13, 0, 0, tzinfo=timezone.utc), 0),
        # These aggregators don't exist
        (4, datetime.min, 0),
        (-1, datetime.min, 0),
    ],
)
@pytest.mark.anyio
async def test_select_aggregator_site_count(
    pg_base_config, aggregator_id: int, changed_after: datetime, expected_count: int
):
    """Simple tests to ensure the counts work for both valid / invalid IDs"""
    async with generate_async_session(pg_base_config) as session:
        assert await select_aggregator_site_count(session, aggregator_id, changed_after) == expected_count


@pytest.mark.anyio
async def test_select_all_sites_with_aggregator_id_contents(pg_base_config):
    """Tests that the returned sites match what's in the DB"""
    async with generate_async_session(pg_base_config) as session:
        # Check fetching all sites for agg 1
        sites = await select_all_sites_with_aggregator_id(session, 2, 0, datetime.min, 100)
        assert_list_type(Site, sites, count=1)
        site_3 = sites[0]
        assert site_3.site_id == 3
        assert site_3.nmi == "3333333333"
        assert site_3.aggregator_id == 2
        assert_datetime_equal(site_3.changed_time, datetime(2022, 2, 3, 8, 9, 10, 500000, tzinfo=timezone.utc))
        assert site_3.lfdi == "site3-lfdi"
        assert site_3.sfdi == 3333
        assert site_3.device_category == DeviceCategory(2)


@pytest.mark.anyio
async def test_select_all_sites_with_aggregator_id_filters(pg_base_config):
    """Tests out the various ways sites can be filtered via the aggregator"""
    async with generate_async_session(pg_base_config) as session:
        # Check fetching all sites for agg 1
        sites = await select_all_sites_with_aggregator_id(session, 1, 0, datetime.min, 100)
        assert_list_type(Site, sites, count=3)
        assert sorted([s.site_id for s in sites]) == [1, 2, 4]  # Checks the id's match our expected filter

        # Change aggregator
        sites = await select_all_sites_with_aggregator_id(session, 2, 0, datetime.min, 100)
        assert_list_type(Site, sites, count=1)
        assert sorted([s.site_id for s in sites]) == [3]  # Checks the id's match our expected filter

        # Empty/missing aggregator
        sites = await select_all_sites_with_aggregator_id(session, 3, 0, datetime.min, 100)
        assert_list_type(Site, sites, count=0)
        sites = await select_all_sites_with_aggregator_id(session, 4, 0, datetime.min, 100)
        assert_list_type(Site, sites, count=0)
        sites = await select_all_sites_with_aggregator_id(session, -1, 0, datetime.min, 100)
        assert_list_type(Site, sites, count=0)
        sites = await select_all_sites_with_aggregator_id(session, 3, 10, datetime.min, 100)
        assert_list_type(Site, sites, count=0)
        sites = await select_all_sites_with_aggregator_id(session, 4, 10, datetime.min, 100)
        assert_list_type(Site, sites, count=0)

        # Add a datetime filter
        sites = await select_all_sites_with_aggregator_id(
            session, 1, 0, datetime(2022, 2, 3, 6, 0, 0, tzinfo=timezone.utc), 100
        )
        assert_list_type(Site, sites, count=1)
        assert sorted([s.site_id for s in sites]) == [4]  # Checks the id's match our expected filter

        # Add a limit filter (remembering that ordering runs off changedTime desc then SFDI)
        sites = await select_all_sites_with_aggregator_id(session, 1, 0, datetime.min, 2)
        assert_list_type(Site, sites, count=2)
        assert sorted([s.site_id for s in sites]) == [2, 4]  # Checks the id's match our expected filter

        # Add a limit filter with a skip (remembering that ordering runs off changedTime desc then SFDI)
        sites = await select_all_sites_with_aggregator_id(session, 1, 1, datetime.min, 2)
        assert_list_type(Site, sites, count=2)
        assert sorted([s.site_id for s in sites]) == [1, 2]  # Checks the id's match our expected filter
        sites = await select_all_sites_with_aggregator_id(session, 1, 2, datetime.min, 2)
        assert_list_type(Site, sites, count=1)
        assert sorted([s.site_id for s in sites]) == [1]  # Checks the id's match our expected filter
        sites = await select_all_sites_with_aggregator_id(session, 1, 3, datetime.min, 2)
        assert_list_type(Site, sites, count=0)
        sites = await select_all_sites_with_aggregator_id(session, 1, 99, datetime.min, 2)
        assert_list_type(Site, sites, count=0)

        # combination date + skip filter
        sites = await select_all_sites_with_aggregator_id(
            session, 1, 1, datetime(2022, 2, 3, 4, 30, 0, tzinfo=timezone.utc), 100
        )
        assert_list_type(Site, sites, count=1)
        assert sorted([s.site_id for s in sites]) == [2]  # Checks the id's match our expected filter


@pytest.mark.parametrize(
    "aggregator_id, aggregator_lfdi, timezone_id",
    [
        (
            1,  # Aggregator 1 has 3 sites
            "9dfdd56f6128cdc894a1e42c690cab197184a8e9",
            "Australia/Brisbane",  # Values for first site under aggregator 1
        ),
        (
            2,  # Aggregator 2 has 1 site
            "403ba02aa36fa072c47eb3299daaafe94399adad",
            "Australia/Brisbane",  # Values for first site under aggregator 2
        ),
        (
            3,  # Aggregator 3 has no sites
            "8ad1d4ce1d3b353ebee21230a89e4172b18f520e",
            "Australia/Brisbane",  # Default timezone if aggregator has no sites
        ),
    ],
)
@pytest.mark.anyio
async def test_get_virtual_site_for_aggregator(
    pg_base_config, aggregator_id: int, aggregator_lfdi: str, timezone_id: str
):
    """Tests that get_virtual_site_for_aggregator creates a suitable virtual site for an aggregator"""

    from envoy_schema.server.schema.sep2.types import DeviceCategory

    async with generate_async_session(pg_base_config) as session:
        virtual_site = await get_virtual_site_for_aggregator(
            session, aggregator_id=aggregator_id, aggregator_lfdi=aggregator_lfdi
        )

        assert virtual_site.site_id == 0  # Virtual sites always have a site_id of 0
        assert virtual_site.aggregator_id == aggregator_id
        assert_nowish(virtual_site.changed_time)  # Virtual sites have a changed time set to when they are requested

        # Virtual sites inherit these values from the first site under the aggregator
        assert virtual_site.lfdi == aggregator_lfdi
        assert virtual_site.sfdi
        assert virtual_site.device_category == DeviceCategory(0)
        assert virtual_site.timezone_id == timezone_id

        assert virtual_site.registration_pin == 0, "This is a nonsensical concept for the aggregator end device"


@pytest.mark.parametrize(
    "aggregator_lfdi",
    [
        (""),  # Empty string not a valid lfdi
        ("LFDI"),  # Contains characters not part of valid hex string
        ("!@#$"),  # Contains characters not part of valid hex string
    ],
)
@pytest.mark.anyio
async def test_get_virtual_site_for_aggregator__raises_exception_with_invalid_lfdi(
    pg_base_config, aggregator_lfdi: str
):
    with pytest.raises(ValueError):
        async with generate_async_session(pg_base_config) as session:
            _ = await get_virtual_site_for_aggregator(session, aggregator_id=1, aggregator_lfdi=aggregator_lfdi)


@pytest.mark.parametrize("aggregator_id", [4, 99])
@pytest.mark.anyio
async def test_get_virtual_site_for_aggregator__no_aggregator(pg_base_config, aggregator_id: int):
    """Tests get_virtual_site_for_aggregator. Returns None if aggregator not present"""
    aggregator_lfdi = "9dfdd56f6128cdc894a1e42c690cab197184a8e9"
    async with generate_async_session(pg_base_config) as session:
        virtual_site = await get_virtual_site_for_aggregator(
            session, aggregator_id=aggregator_id, aggregator_lfdi=aggregator_lfdi
        )
        assert virtual_site is None


@pytest.mark.parametrize("aggregator_id, first_site_id", [(1, 1), (2, 3)])
@pytest.mark.anyio
async def test_select_first_site_under_aggregator(pg_base_config, aggregator_id: int, first_site_id: Optional[int]):
    """Tests select_first_site_under_aggregator. Returns first site under aggregator"""
    async with generate_async_session(pg_base_config) as session:
        site = await select_first_site_under_aggregator(session, aggregator_id=aggregator_id)
        assert site.site_id == first_site_id


@pytest.mark.parametrize("aggregator_id", [3])
@pytest.mark.anyio
async def test_select_first_site_under_aggregator__no_sites(pg_base_config, aggregator_id: int):
    """Tests select_first_site_under_aggregator. Returns None if aggregator has no sites"""
    async with generate_async_session(pg_base_config) as session:
        site = await select_first_site_under_aggregator(session, aggregator_id=aggregator_id)
        assert site is None


@pytest.mark.parametrize("aggregator_id", [4, 99])
@pytest.mark.anyio
async def test_select_first_site_under_aggregator__no_aggregator(pg_base_config, aggregator_id: int):
    """Tests select_first_site_under_aggregator. Returns None if aggregator not present"""
    async with generate_async_session(pg_base_config) as session:
        site = await select_first_site_under_aggregator(session, aggregator_id=aggregator_id)
        assert site is None


@pytest.mark.parametrize(
    "site_id, agg_id, expected_vals",
    [
        (
            3,
            2,
            (
                "3333333333",
                "site3-lfdi",
                3333,
                DeviceCategory(2),
                datetime(2022, 2, 3, 8, 9, 10, 500000, tzinfo=timezone.utc),
            ),
        ),
        (
            1,
            1,
            (
                "1111111111",
                "site1-lfdi",
                1111,
                DeviceCategory(0),
                datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc),
            ),
        ),
        # test mismatched ids
        (1, 2, None),
        (3, 1, None),
        (3, 3, None),
        # test bad ids
        (1, 99, None),
        (99, 1, None),
        (-1, -1, None),
    ],
)
@pytest.mark.anyio
async def test_select_single_site_with_site_id(
    pg_base_config, site_id: int, agg_id: int, expected_vals: Optional[tuple[str, str, int, DeviceCategory, datetime]]
):
    """Tests that the returned objects match the DB contents (and handle lookup misses)"""
    async with generate_async_session(pg_base_config) as session:
        site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=agg_id)

        if expected_vals is None:
            assert site is None
        else:
            (nmi, lfdi, sfdi, dc, changed_time) = expected_vals
            assert isinstance(site, Site)
            assert site.site_id == site_id
            assert site.aggregator_id == agg_id
            assert site.nmi == nmi
            assert site.lfdi == lfdi
            assert site.sfdi == sfdi
            assert site.device_category == dc
            assert_datetime_equal(site.changed_time, changed_time)


@pytest.mark.parametrize(
    "sfdi, agg_id, expected_vals",
    [
        (
            3333,
            2,
            (
                3,
                "3333333333",
                "site3-lfdi",
                DeviceCategory(2),
                datetime(2022, 2, 3, 8, 9, 10, 500000, tzinfo=timezone.utc),
            ),
        ),
        (
            1111,
            1,
            (
                1,
                "1111111111",
                "site1-lfdi",
                DeviceCategory(0),
                datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc),
            ),
        ),
        # test mismatched ids
        (1111, 2, None),
        (3333, 1, None),
        (3333, 3, None),
        # test bad ids
        (1, 1, None),
        (1111, 99, None),
        (99, 1, None),
        (-1, -1, None),
    ],
)
@pytest.mark.anyio
async def test_select_single_site_with_sfdi(
    pg_base_config, sfdi: int, agg_id: int, expected_vals: Optional[tuple[int, str, str, DeviceCategory, datetime]]
):
    """Tests that the returned objects match the DB contents (and handle lookup misses)"""
    async with generate_async_session(pg_base_config) as session:
        site = await select_single_site_with_sfdi(session, sfdi=sfdi, aggregator_id=agg_id)

        if expected_vals is None:
            assert site is None
        else:
            (site_id, nmi, lfdi, dc, changed_time) = expected_vals
            assert isinstance(site, Site)
            assert site.site_id == site_id
            assert site.aggregator_id == agg_id
            assert site.nmi == nmi
            assert site.lfdi == lfdi
            assert site.sfdi == sfdi
            assert site.device_category == dc
            assert_datetime_equal(site.changed_time, changed_time)


@pytest.mark.anyio
async def test_select_single_site_with_lfdi(pg_base_config):
    """Tests that the returned objects match the DB contents (and handle lookup misses)"""
    async with generate_async_session(pg_base_config) as session:
        # Site 3 for Agg 2
        site_3 = await select_single_site_with_lfdi(session, "site3-lfdi", 2)
        assert isinstance(site_3, Site)
        assert site_3.site_id == 3
        assert site_3.nmi == "3333333333"
        assert site_3.aggregator_id == 2
        assert_datetime_equal(site_3.changed_time, datetime(2022, 2, 3, 8, 9, 10, 500000, tzinfo=timezone.utc))
        assert site_3.lfdi == "site3-lfdi"
        assert site_3.sfdi == 3333
        assert site_3.device_category == DeviceCategory(2)

        # Site 1 for Agg 1
        site_1 = await select_single_site_with_lfdi(session, "site1-lfdi", 1)
        assert isinstance(site_1, Site)
        assert site_1.site_id == 1
        assert site_1.nmi == "1111111111"
        assert site_1.aggregator_id == 1
        assert_datetime_equal(site_1.changed_time, datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc))
        assert site_1.lfdi == "site1-lfdi"
        assert site_1.sfdi == 1111
        assert site_1.device_category == DeviceCategory(0)

        # test mismatched ids
        assert await select_single_site_with_lfdi(session, "site1-lfdi", 2) is None
        assert await select_single_site_with_lfdi(session, "site3-lfdi", 1) is None
        assert await select_single_site_with_lfdi(session, "site3-lfdi", 3) is None

        # test bad ids
        assert await select_single_site_with_lfdi(session, "site1-lfdi", 99) is None
        assert await select_single_site_with_lfdi(session, "site99-lfdi", 1) is None
        assert await select_single_site_with_lfdi(session, "", -1) is None


@pytest.mark.anyio
async def test_upsert_site_for_aggregator_insert(pg_base_config):
    """Tests that the upsert can do inserts"""

    # Do the insert in a session separate to the database
    inserted_id: int
    new_site: Site = generate_class_instance(Site)
    del new_site.site_id  # Don't set the primary key - we expect the DB to set that
    async with generate_async_session(pg_base_config) as session:
        inserted_id = await upsert_site_for_aggregator(session, 1, new_site)
        assert inserted_id
        await session.commit()

    # Validate the state of the DB in a new session
    async with generate_async_session(pg_base_config) as session:
        # check it exists
        inserted_site = await select_single_site_with_site_id(session, inserted_id, 1)
        assert inserted_site
        assert_nowish(inserted_site.created_time)  # This should be set by the DB
        assert_class_instance_equality(Site, new_site, inserted_site, ignored_properties={"site_id", "created_time"})

        # Sanity check another site in the same aggregator
        site_1 = await select_single_site_with_site_id(session, 1, 1)
        assert isinstance(site_1, Site)
        assert site_1.site_id == 1
        assert site_1.nmi == "1111111111"
        assert site_1.aggregator_id == 1
        assert_datetime_equal(site_1.changed_time, datetime(2022, 2, 3, 4, 5, 6, 500000, tzinfo=timezone.utc))
        assert site_1.lfdi == "site1-lfdi"
        assert site_1.sfdi == 1111
        assert site_1.device_category == DeviceCategory(0)
        assert site_1.registration_pin == 11111

        # Sanity check the site count
        assert await select_aggregator_site_count(session, 1, datetime.min) == 4
        assert await select_aggregator_site_count(session, 2, datetime.min) == 1
        assert await select_aggregator_site_count(session, 3, datetime.min) == 0

        # This is a new row - therefore nothing should be copied to the archive
        assert (await session.execute(select(func.count()).select_from(ArchiveSite))).scalar_one() == 0


@pytest.mark.anyio
async def test_upsert_site_for_aggregator_update_non_indexed(pg_base_config):
    """Tests that the upsert can do updates to fields that aren't unique constrained"""

    # We want the site object we upsert to be a "fresh" Site instance that hasn't been anywhere near
    # a SQL Alchemy session but shares the appropriate indexed values
    site_id_to_update = 1
    aggregator_id = 1
    site_to_upsert: Site = generate_class_instance(Site)
    existing_registration_pin: int
    async with generate_async_session(pg_base_config) as session:
        existing_site = await select_single_site_with_site_id(session, site_id_to_update, aggregator_id)
        assert existing_site

        # Copy across the indexed values as we don't want to update those
        site_to_upsert.lfdi = existing_site.lfdi
        site_to_upsert.sfdi = existing_site.sfdi
        site_to_upsert.aggregator_id = existing_site.aggregator_id
        site_to_upsert.site_id = existing_site.site_id
        existing_registration_pin = existing_site.registration_pin
    assert existing_registration_pin != site_to_upsert.registration_pin, "Need to be different for test to be valid"

    # Perform the upsert in a new session
    async with generate_async_session(pg_base_config) as session:
        updated_id = await upsert_site_for_aggregator(session, aggregator_id, site_to_upsert)
        assert updated_id == site_id_to_update
        await session.commit()

    # Validate the state of the DB in a new session
    async with generate_async_session(pg_base_config) as session:
        # check it exists
        site_db = await select_single_site_with_site_id(session, site_id_to_update, aggregator_id)

        assert_class_instance_equality(
            Site, site_to_upsert, site_db, ignored_properties={"site_id", "created_time", "registration_pin"}
        )
        assert_datetime_equal(site_db.created_time, datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc))  # Not updated
        assert site_db.registration_pin == existing_registration_pin, "We don't want UPDATEs changing the PIN"

        # Sanity check another site in the same aggregator
        site_2 = await select_single_site_with_site_id(session, 2, aggregator_id)
        assert isinstance(site_2, Site)
        assert site_2.site_id == 2
        assert site_2.nmi == "2222222222"
        assert site_2.aggregator_id == aggregator_id
        assert_datetime_equal(site_2.changed_time, datetime(2022, 2, 3, 5, 6, 7, 500000, tzinfo=timezone.utc))
        assert site_2.lfdi == "site2-lfdi"
        assert site_2.sfdi == 2222
        assert site_2.device_category == DeviceCategory(1)
        assert site_2.registration_pin == 22222

        # Sanity check the site count
        assert await select_aggregator_site_count(session, 1, datetime.min) == 3
        assert await select_aggregator_site_count(session, 2, datetime.min) == 1
        assert await select_aggregator_site_count(session, 3, datetime.min) == 0

        # This is an updated row - therefore we should have a new archived site containing the original data
        assert (await session.execute(select(func.count()).select_from(ArchiveSite))).scalar_one() == 1
        archive_data = (await session.execute(select(ArchiveSite))).scalar_one()

        assert_class_instance_equality(
            Site,
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
                registration_pin=11111,
            ),
            archive_data,
        )
        assert_nowish(archive_data.archive_time)
        assert archive_data.deleted_time is None


@pytest.mark.anyio
async def test_upsert_site_for_aggregator_cant_change_agg_id(pg_base_config):
    """Tests that attempting to sneak through a mismatched agg_id results in an exception with no changes"""
    site_id_to_update = 1
    aggregator_id = 1

    original_site: Site
    update_attempt_site: Site
    original_registration_pin: int
    async with generate_async_session(pg_base_config) as session:
        original_site = await select_single_site_with_site_id(session, site_id_to_update, aggregator_id)
        assert original_site
        original_registration_pin = original_site.registration_pin

        update_attempt_site = clone_class_instance(original_site, ignored_properties=set(["assignments", "site_ders"]))
        update_attempt_site.aggregator_id = 3
        update_attempt_site.nmi = "new-nmi"

    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(ValueError):
            await upsert_site_for_aggregator(session, aggregator_id, update_attempt_site)

        # db should be unmodified
        site_db = await select_single_site_with_site_id(session, update_attempt_site.site_id, aggregator_id)
        assert site_db
        assert site_db.nmi == original_site.nmi, "nmi should NOT have changed"
        assert site_db.aggregator_id == original_site.aggregator_id, "aggregator_id should NOT have changed"
        assert site_db.registration_pin == original_registration_pin, "registration_pin should NOT have changed"

        # Sanity check the site count hasn't changed
        assert await select_aggregator_site_count(session, 1, datetime.min) == 3
        assert await select_aggregator_site_count(session, 2, datetime.min) == 1
        assert await select_aggregator_site_count(session, 3, datetime.min) == 0


@dataclass
class SnapshotTableCount:
    """Moment in time snapshot of rows in table/archive"""

    t: type[Base]  # The table type
    archive_t: type[ArchiveBase]  # the archive table type
    total_count: int  # Total rows in the table
    filtered_count: int  # Totals rows in the table (that pass the site/aggregator filter)
    archive_count: int  # Total rows in the equivalent table archive


async def count_table_rows(
    session: AsyncSession,
    t: type[Base],
    join_t: Optional[Union[type[Base], list[type[Base]]]],
    archive_t: type[ArchiveBase],
    where_clause: Callable[[Select[int]], Select[int]],
) -> SnapshotTableCount:
    """Counts the number of rows in the specified source table for t. Also counts again, but with the where_clause
    applied to the query.

    if join_t is not None, the count queries will be joined to this type (allowing filtering against this table). This
    can be a list of a singular type

    Returns (total_count, filtered_count)"""
    q = select(func.count()).select_from(t)

    if join_t is not None:
        if isinstance(join_t, list):
            for jt in join_t:
                q = q.join(jt)
        else:
            q = q.join(join_t)

    total_count = (await session.execute(q)).scalar_one()
    filtered_count = (await session.execute(where_clause(q))).scalar_one()
    archive_count = (await session.execute(select(func.count()).select_from(archive_t))).scalar_one()

    return SnapshotTableCount(
        t, archive_t, total_count=total_count, filtered_count=filtered_count, archive_count=archive_count
    )


async def snapshot_all_site_tables(session: AsyncSession, agg_id: int, site_id: int) -> list[SnapshotTableCount]:
    """Snapshots the site table and all downstream child tables"""
    snapshot: list[SnapshotTableCount] = []

    snapshot.append(
        await count_table_rows(
            session,
            Site,
            None,
            ArchiveSite,
            lambda q: q.where(Site.site_id == site_id).where(Site.aggregator_id == agg_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteReadingType,
            None,
            ArchiveSiteReadingType,
            lambda q: q.where(SiteReadingType.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteReading,
            SiteReadingType,
            ArchiveSiteReading,
            lambda q: q.where(SiteReadingType.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            Subscription,
            None,
            ArchiveSubscription,
            lambda q: q.where(Subscription.scoped_site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SubscriptionCondition,
            Subscription,
            ArchiveSubscriptionCondition,
            lambda q: q.where(Subscription.scoped_site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteDER,
            Site,
            ArchiveSiteDER,
            lambda q: q.where(SiteDER.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteDERAvailability,
            SiteDER,
            ArchiveSiteDERAvailability,
            lambda q: q.where(SiteDER.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteDERRating,
            SiteDER,
            ArchiveSiteDERRating,
            lambda q: q.where(SiteDER.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteDERSetting,
            SiteDER,
            ArchiveSiteDERSetting,
            lambda q: q.where(SiteDER.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            SiteDERStatus,
            SiteDER,
            ArchiveSiteDERStatus,
            lambda q: q.where(SiteDER.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            DynamicOperatingEnvelope,
            None,
            ArchiveDynamicOperatingEnvelope,
            lambda q: q.where(DynamicOperatingEnvelope.site_id == site_id),
        )
    )

    snapshot.append(
        await count_table_rows(
            session,
            TariffGeneratedRate,
            None,
            ArchiveTariffGeneratedRate,
            lambda q: q.where(TariffGeneratedRate.site_id == site_id),
        )
    )

    return snapshot


@pytest.mark.parametrize(
    "site_id, agg_id, expected_delete, commit",
    [
        (s, a, d, c)
        for (s, a, d), c in product(
            [
                (1, 1, True),  # Delete site 1
                (2, 1, True),  # Delete site 2
                (3, 2, True),  # Delete site 3 (different aggregator)
                (4, 1, True),  # Delete site 4 (has no data)
                (5, 0, True),  # Delete site 5 (Null aggregator)
                (6, 0, True),  # Delete site 6 (Null aggregator)
                (1, 0, False),  # Wrong aggregator ID
                (1, 2, False),  # Wrong aggregator ID
                (1, 3, False),  # Wrong aggregator ID
                (1, 99, False),  # Wrong aggregator ID
                (99, 1, False),  # Wrong site ID
            ],
            [True, False],  # Run every test case with a commit = True and commit = False
        )
    ],
)
@pytest.mark.anyio
async def test_delete_site_for_aggregator(
    pg_base_config, site_id: int, agg_id: int, commit: bool, expected_delete: int
):
    """Tests that deleting an entire site cleans up and archives all associated data correctly. Also tests
    that the operation correctly runs inside a session transaction and can be wound back (if required)

    There is an assumption that the underlying archive functions are used - this is just making sure that
    the removal:
        1) Removes the correct records
        2) Archives the correct records
        3) Doesn't delete anything else it shouldn't
    """

    # Count everything before the delete
    async with generate_async_session(pg_base_config) as session:
        snapshot_before = await snapshot_all_site_tables(session, agg_id=agg_id, site_id=site_id)

    # Perform the delete
    now = utc_now()
    deleted_time = datetime(2014, 11, 15, 2, 4, 5, 755, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        actual = await delete_site_for_aggregator(session, agg_id, site_id, deleted_time)
        assert expected_delete == actual

        if commit:
            await session.commit()
            delete_occurred = actual
        else:
            delete_occurred = False

    # Now check the DB / Archive to ensure everything moved as expected
    async with generate_async_session(pg_base_config) as session:
        snapshot_after = await snapshot_all_site_tables(session, agg_id=agg_id, site_id=site_id)

    # Compare our before/after snapshots based on whether a delete occurred (or didn't)
    for before, after in zip(snapshot_before, snapshot_after):
        assert before.t == after.t, "This is a sanity check on snapshot_all_site_tables doing a consistent order"
        assert before.archive_t == after.archive_t, "This is a sanity check on snapshot_all_site_tables"
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
        site = await select_single_site_with_site_id(session, site_id=site_id, aggregator_id=agg_id)
        if commit:
            assert site is None, "Site should NOT be fetchable if the deleted was committed"
        elif expected_delete:
            assert site is not None, "If the delete was NOT committed - the site should still exist"
        else:
            assert site is None, "If the delete was NOT committed but the site DNE - it should continue to not exist"
