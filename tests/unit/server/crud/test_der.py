from datetime import datetime, timezone

import pytest
from assertical.asserts.time import assert_datetime_equal
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.der import InverterStatusType

from envoy.server.crud.der import generate_default_site_der, select_site_der_for_site
from envoy.server.model.site import SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus


def test_generate_default_site_der():
    """Simple sanity check - do we get a SiteDER object back"""
    changed_time = datetime(2022, 1, 2, 3, 4, 5)
    site_der = generate_default_site_der(22, changed_time)
    assert isinstance(site_der, SiteDER)
    assert site_der.site_der_id is None
    assert site_der.site_id == 22
    assert_datetime_equal(changed_time, site_der.changed_time)


@pytest.mark.parametrize("aggregator_id, site_id", [(2, 1), (1, 99), (99, 1)])
@pytest.mark.anyio
async def test_select_site_der_for_site_invalid_lookup(pg_base_config, aggregator_id: int, site_id: int):
    """Tests the various ways DER lookup can fail"""

    async with generate_async_session(pg_base_config) as session:
        assert await select_site_der_for_site(session, aggregator_id, site_id) is None


@pytest.mark.anyio
async def test_select_site_der_for_site_with_relationships(pg_base_config):
    """Tests that the various relationships on SiteDER return without issue"""
    # Now fetch things to validate the relationships map OK and populate matching the values that went in
    async with generate_async_session(pg_base_config) as session:
        site_1_der = await select_site_der_for_site(session, 1, 1)

        assert isinstance(site_1_der, SiteDER)
        assert site_1_der.site_id == 1
        assert site_1_der.site_der_id == 2
        assert_datetime_equal(site_1_der.changed_time, datetime(2024, 3, 14, 5, 55, 44, 500000, tzinfo=timezone.utc))
        assert isinstance(site_1_der.site_der_availability, SiteDERAvailability)
        assert isinstance(site_1_der.site_der_rating, SiteDERRating)
        assert isinstance(site_1_der.site_der_setting, SiteDERSetting)
        assert isinstance(site_1_der.site_der_status, SiteDERStatus)

        # quick sanity check to see we got the right record (these values are pulled direct from base_config.sql)
        assert site_1_der.site_der_availability.availability_duration_sec == 202
        assert site_1_der.site_der_rating.max_a_value == 106
        assert site_1_der.site_der_setting.es_delay == 406
        assert site_1_der.site_der_status.inverter_status == InverterStatusType.MANUFACTURER_STATUS

        # Site 2 DER has no relationships
        site_2_der = await select_site_der_for_site(session, 1, 2)
        assert site_2_der.site_id == 2
        assert site_2_der.site_der_id == 1
        assert_datetime_equal(site_2_der.changed_time, datetime(2024, 3, 14, 4, 55, 44, 500000, tzinfo=timezone.utc))

        assert isinstance(site_2_der, SiteDER)
        assert site_2_der.site_der_availability is None
        assert site_2_der.site_der_rating is None
        assert site_2_der.site_der_setting is None
        assert site_2_der.site_der_status is None
