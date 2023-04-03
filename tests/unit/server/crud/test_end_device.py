from datetime import datetime

import pytest

from envoy.server.crud.end_device import (
    select_aggregator_site_count,
    select_all_sites_with_aggregator_id,
    select_single_site_with_site_id,
    upsert_site_for_aggregator,
)
from envoy.server.model.site import Site
from tests.assert_type import assert_list_type
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_select_aggregator_site_count(pg_base_config):
    """Simple tests to ensure the counts work for both valid / invalid IDs"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        assert await select_aggregator_site_count(session, 1) == 3
        assert await select_aggregator_site_count(session, 2) == 1
        assert await select_aggregator_site_count(session, 3) == 0

        # These aggregators don't exist
        assert await select_aggregator_site_count(session, 4) == 0
        assert await select_aggregator_site_count(session, -1) == 0


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
        assert site_3.changed_time.timestamp() == datetime(2022, 2, 3, 8, 9, 10).timestamp()
        assert site_3.lfdi == 'site3-lfdi'
        assert site_3.sfdi == 3333


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
        sites = await select_all_sites_with_aggregator_id(session, 1, 0, datetime(2022, 2, 3, 6, 0, 0), 100)
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
        sites = await select_all_sites_with_aggregator_id(session, 1, 1, datetime(2022, 2, 3, 4, 30, 0), 100)
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
        assert site_3.changed_time.timestamp() == datetime(2022, 2, 3, 8, 9, 10).timestamp()
        assert site_3.lfdi == 'site3-lfdi'
        assert site_3.sfdi == 3333

        # Site 1 for Agg 1
        site_1 = await select_single_site_with_site_id(session, 1, 1)
        assert type(site_1) == Site
        assert site_1.site_id == 1
        assert site_1.nmi == "1111111111"
        assert site_1.aggregator_id == 1
        assert site_1.changed_time.timestamp() == datetime(2022, 2, 3, 4, 5, 6).timestamp()
        assert site_1.lfdi == 'site1-lfdi'
        assert site_1.sfdi == 1111

        # test mismatched ids
        assert await select_single_site_with_site_id(session, 1, 2) is None
        assert await select_single_site_with_site_id(session, 3, 1) is None
        assert await select_single_site_with_site_id(session, 3, 3) is None

        # test bad ids
        assert await select_single_site_with_site_id(session, 1, 99) is None
        assert await select_single_site_with_site_id(session, 99, 1) is None
        assert await select_single_site_with_site_id(session, -1, -1) is None


@pytest.mark.anyio
async def test_upsert_site_for_aggregator_insert(pg_base_config):
    """Tests that the upsert can do inserts"""

    # Do the insert in a session seperate to the database
    inserted_id: int
    new_site = Site(nmi="new-nmi", aggregator_id=1, changed_time=datetime.now(), lfdi="new-lfdi", sfdi=1234)
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

        # Sanity check another site
        site_1 = await select_single_site_with_site_id(session, 1, 1)
        assert type(site_1) == Site
        assert site_1.site_id == 1
        assert site_1.nmi == "1111111111"
        assert site_1.aggregator_id == 1
        assert site_1.changed_time.timestamp() == datetime(2022, 2, 3, 4, 5, 6).timestamp()
        assert site_1.lfdi == 'site1-lfdi'
        assert site_1.sfdi == 1111

        # Sanity check the site count
        assert await select_aggregator_site_count(session, 1) == 3
        assert await select_aggregator_site_count(session, 2) == 1
        assert await select_aggregator_site_count(session, 3) == 0
