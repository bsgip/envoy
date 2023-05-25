from datetime import datetime, timezone

import pytest

from envoy.server.crud.end_device import (
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_single_site_with_lfdi,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.model.site import Site
from envoy.server.schema.sep2.types import DeviceCategory
from tests.assert_time import assert_datetime_equal
from tests.assert_type import assert_list_type
from tests.data.fake.generator import clone_class_instance, generate_class_instance
from tests.postgres_testing import generate_async_session


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
        assert_datetime_equal(site_3.changed_time, datetime(2022, 2, 3, 8, 9, 10, tzinfo=timezone.utc))
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


@pytest.mark.anyio
async def test_select_single_site_with_site_id(pg_base_config):
    """Tests that the returned objects match the DB contents (and handle lookup misses)"""
    async with generate_async_session(pg_base_config) as session:
        # Site 3 for Agg 2
        site_3 = await select_single_site_with_site_id(session, 3, 2)
        assert type(site_3) == Site
        assert site_3.site_id == 3
        assert site_3.nmi == "3333333333"
        assert site_3.aggregator_id == 2
        assert_datetime_equal(site_3.changed_time, datetime(2022, 2, 3, 8, 9, 10, tzinfo=timezone.utc))
        assert site_3.lfdi == "site3-lfdi"
        assert site_3.sfdi == 3333
        assert site_3.device_category == DeviceCategory(2)

        # Site 1 for Agg 1
        site_1 = await select_single_site_with_site_id(session, 1, 1)
        assert type(site_1) == Site
        assert site_1.site_id == 1
        assert site_1.nmi == "1111111111"
        assert site_1.aggregator_id == 1
        assert_datetime_equal(site_1.changed_time, datetime(2022, 2, 3, 4, 5, 6, tzinfo=timezone.utc))
        assert site_1.lfdi == "site1-lfdi"
        assert site_1.sfdi == 1111
        assert site_1.device_category == DeviceCategory(0)

        # test mismatched ids
        assert await select_single_site_with_site_id(session, 1, 2) is None
        assert await select_single_site_with_site_id(session, 3, 1) is None
        assert await select_single_site_with_site_id(session, 3, 3) is None

        # test bad ids
        assert await select_single_site_with_site_id(session, 1, 99) is None
        assert await select_single_site_with_site_id(session, 99, 1) is None
        assert await select_single_site_with_site_id(session, -1, -1) is None


@pytest.mark.anyio
async def test_select_single_site_with_lfdi(pg_base_config):
    """Tests that the returned objects match the DB contents (and handle lookup misses)"""
    async with generate_async_session(pg_base_config) as session:
        # Site 3 for Agg 2
        site_3 = await select_single_site_with_lfdi(session, "site3-lfdi", 2)
        assert type(site_3) == Site
        assert site_3.site_id == 3
        assert site_3.nmi == "3333333333"
        assert site_3.aggregator_id == 2
        assert_datetime_equal(site_3.changed_time, datetime(2022, 2, 3, 8, 9, 10, tzinfo=timezone.utc))
        assert site_3.lfdi == "site3-lfdi"
        assert site_3.sfdi == 3333
        assert site_3.device_category == DeviceCategory(2)

        # Site 1 for Agg 1
        site_1 = await select_single_site_with_lfdi(session, "site1-lfdi", 1)
        assert type(site_1) == Site
        assert site_1.site_id == 1
        assert site_1.nmi == "1111111111"
        assert site_1.aggregator_id == 1
        assert_datetime_equal(site_1.changed_time, datetime(2022, 2, 3, 4, 5, 6, tzinfo=timezone.utc))
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
        assert inserted_site.nmi == new_site.nmi
        assert inserted_site.aggregator_id == new_site.aggregator_id
        assert inserted_site.changed_time.timestamp() == new_site.changed_time.timestamp()
        assert inserted_site.lfdi == new_site.lfdi
        assert inserted_site.sfdi == new_site.sfdi
        assert inserted_site.device_category == new_site.device_category

        # Sanity check another site in the same aggregator
        site_1 = await select_single_site_with_site_id(session, 1, 1)
        assert type(site_1) == Site
        assert site_1.site_id == 1
        assert site_1.nmi == "1111111111"
        assert site_1.aggregator_id == 1
        assert_datetime_equal(site_1.changed_time, datetime(2022, 2, 3, 4, 5, 6, tzinfo=timezone.utc))
        assert site_1.lfdi == "site1-lfdi"
        assert site_1.sfdi == 1111
        assert site_1.device_category == DeviceCategory(0)

        # Sanity check the site count
        assert await select_aggregator_site_count(session, 1, datetime.min) == 4
        assert await select_aggregator_site_count(session, 2, datetime.min) == 1
        assert await select_aggregator_site_count(session, 3, datetime.min) == 0


@pytest.mark.anyio
async def test_upsert_site_for_aggregator_update_non_indexed(pg_base_config):
    """Tests that the upsert can do updates to fields that aren't unique constrained"""

    # We want the site object we upsert to be a "fresh" Site instance that hasn't been anywhere near
    # a SQL Alchemy session but shares the appropriate indexed values
    site_id_to_update = 1
    aggregator_id = 1
    site_to_upsert: Site = generate_class_instance(Site)
    async with generate_async_session(pg_base_config) as session:
        existing_site = await select_single_site_with_site_id(session, site_id_to_update, aggregator_id)
        assert existing_site

        # Copy across the indexed values as we don't want to update those
        site_to_upsert.lfdi = existing_site.lfdi
        site_to_upsert.sfdi = existing_site.sfdi
        site_to_upsert.aggregator_id = existing_site.aggregator_id
        site_to_upsert.site_id = existing_site.site_id

    # Perform the upsert in a new session
    async with generate_async_session(pg_base_config) as session:
        updated_id = await upsert_site_for_aggregator(session, aggregator_id, site_to_upsert)
        assert updated_id == site_id_to_update
        await session.commit()

    # Validate the state of the DB in a new session
    async with generate_async_session(pg_base_config) as session:
        # check it exists
        site_db = await select_single_site_with_site_id(session, site_id_to_update, aggregator_id)
        assert site_db
        assert site_db.nmi == site_to_upsert.nmi
        assert site_db.aggregator_id == site_to_upsert.aggregator_id
        assert_datetime_equal(site_db.changed_time, site_to_upsert.changed_time)
        assert site_db.lfdi == site_to_upsert.lfdi
        assert site_db.sfdi == site_to_upsert.sfdi
        assert site_db.device_category == site_to_upsert.device_category
        assert site_db.timezone_id == site_to_upsert.timezone_id

        # Sanity check another site in the same aggregator
        site_2 = await select_single_site_with_site_id(session, 2, aggregator_id)
        assert type(site_2) == Site
        assert site_2.site_id == 2
        assert site_2.nmi == "2222222222"
        assert site_2.aggregator_id == aggregator_id
        assert_datetime_equal(site_2.changed_time, datetime(2022, 2, 3, 5, 6, 7, tzinfo=timezone.utc))
        assert site_2.lfdi == "site2-lfdi"
        assert site_2.sfdi == 2222
        assert site_2.device_category == DeviceCategory(1)

        # Sanity check the site count
        assert await select_aggregator_site_count(session, 1, datetime.min) == 3
        assert await select_aggregator_site_count(session, 2, datetime.min) == 1
        assert await select_aggregator_site_count(session, 3, datetime.min) == 0


@pytest.mark.anyio
async def test_upsert_site_for_aggregator_cant_change_agg_id(pg_base_config):
    """Tests that attempting to sneak through a mismatched agg_id results in an exception with no changes"""
    site_id_to_update = 1
    aggregator_id = 1

    original_site: Site
    update_attempt_site: Site
    async with generate_async_session(pg_base_config) as session:
        original_site = await select_single_site_with_site_id(session, site_id_to_update, aggregator_id)
        assert original_site

        update_attempt_site = clone_class_instance(original_site)
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

        # Sanity check the site count hasn't changed
        assert await select_aggregator_site_count(session, 1, datetime.min) == 3
        assert await select_aggregator_site_count(session, 2, datetime.min) == 1
        assert await select_aggregator_site_count(session, 3, datetime.min) == 0
