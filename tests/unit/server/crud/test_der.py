from datetime import UTC, datetime

import pytest
from assertical.asserts.time import assert_datetime_equal
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.der import InverterStatusType
from sqlalchemy import select

from envoy.server.crud.der import (
    select_der_changed_time_for_site,
    select_site_der_availability_for_site,
    select_site_der_rating_for_site,
    select_site_der_setting_for_site,
    select_site_der_status_for_site,
)
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus


@pytest.mark.anyio
async def test_select_site_der_children_for_site(pg_base_config):
    """Site 1 has all four DER sub resources - they should each fetch with the expected values from base_config.sql"""
    async with generate_async_session(pg_base_config) as session:
        rating = await select_site_der_rating_for_site(session, 1)
        setting = await select_site_der_setting_for_site(session, 1)
        availability = await select_site_der_availability_for_site(session, 1)
        status = await select_site_der_status_for_site(session, 1)

        assert isinstance(rating, SiteDERRating)
        assert rating.site_id == 1
        assert rating.max_a_value == 106
        assert isinstance(setting, SiteDERSetting)
        assert setting.site_id == 1
        assert setting.es_delay == 406
        assert isinstance(availability, SiteDERAvailability)
        assert availability.site_id == 1
        assert availability.availability_duration_sec == 202
        assert isinstance(status, SiteDERStatus)
        assert status.site_id == 1
        assert status.inverter_status == InverterStatusType.MANUFACTURER_STATUS


@pytest.mark.parametrize("site_id", [2, 99])
@pytest.mark.anyio
async def test_select_site_der_children_for_site_none(pg_base_config, site_id: int):
    """Sites without any DER data (or that don't exist) return None for each sub resource"""
    async with generate_async_session(pg_base_config) as session:
        assert await select_site_der_rating_for_site(session, site_id) is None
        assert await select_site_der_setting_for_site(session, site_id) is None
        assert await select_site_der_availability_for_site(session, site_id) is None
        assert await select_site_der_status_for_site(session, site_id) is None


@pytest.mark.anyio
async def test_select_der_changed_time_for_site_with_children(pg_base_config):
    """The (virtual) DER changed_time is the most recent change across its sub resources"""
    async with generate_async_session(pg_base_config) as session:
        site = (await session.execute(select(Site).where(Site.site_id == 1))).scalar_one()
        changed_time = await select_der_changed_time_for_site(session, site)
        # Site 1's most recently changed sub resource is the status at 2022-11-01 11:05:04.5
        assert_datetime_equal(changed_time, datetime(2022, 11, 1, 11, 5, 4, 500000, tzinfo=UTC))


@pytest.mark.anyio
async def test_select_der_changed_time_for_site_no_children(pg_base_config):
    """With no DER data the changed_time falls back to the site's own changed_time"""
    async with generate_async_session(pg_base_config) as session:
        site = (await session.execute(select(Site).where(Site.site_id == 2))).scalar_one()
        changed_time = await select_der_changed_time_for_site(session, site)
        assert_datetime_equal(changed_time, site.changed_time)
