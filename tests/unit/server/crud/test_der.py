from datetime import datetime, timezone

import pytest

from envoy.server.crud.der import generate_default_site_der, select_site_der_for_site
from envoy.server.model.site import SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from tests.assert_time import assert_datetime_equal, assert_nowish
from tests.data.fake.generator import assert_class_instance_equality, clone_class_instance, generate_class_instance
from tests.postgres_testing import generate_async_session


def test_generate_default_site_der():
    """Simple sanity check - do we get a SiteDER object back"""
    site_der = generate_default_site_der(11, 22)
    assert isinstance(site_der, SiteDER)
    assert site_der.site_der_id == 11
    assert site_der.site_id == 22
    assert_nowish(site_der.changed_time)


@pytest.mark.parametrize("aggregator_id, site_id", [(2, 1), (1, 99), (99, 1)])
@pytest.mark.anyio
async def test_select_site_der_for_site_invalid_lookup(pg_base_config, aggregator_id: int, site_id: int):
    """Tests the various ways DER lookup can fail"""

    async with generate_async_session(pg_base_config) as session:
        assert await select_site_der_for_site(session, aggregator_id, site_id) is None


@pytest.mark.anyio
async def test_select_site_der_for_site_with_relationships(pg_base_config):
    """Tests that the various relationships on SiteDER return without issue"""
    # Start by loading up the site_1_der with all relationships and pushing it back to the DB
    der_avail: SiteDERAvailability = generate_class_instance(SiteDERAvailability, seed=101)
    der_avail.site_der_id = 2  # DER 2 belongs to site 1
    del der_avail.site_der_availability_id
    der_rating: SiteDERRating = generate_class_instance(SiteDERRating, seed=202)
    der_rating.site_der_id = 2  # DER 2 belongs to site 1
    del der_rating.site_der_rating_id
    der_setting: SiteDERSetting = generate_class_instance(SiteDERSetting, seed=303)
    der_setting.site_der_id = 2  # DER 2 belongs to site 1
    del der_setting.site_der_setting_id
    der_status: SiteDERStatus = generate_class_instance(SiteDERStatus, seed=404)
    der_status.site_der_id = 2  # DER 2 belongs to site 1
    del der_status.site_der_status_id
    der_status.manufacturer_status = "smlval"  # This has to fit within the DB field
    async with generate_async_session(pg_base_config) as session:
        site_1_der = await select_site_der_for_site(session, 1, 1)
        assert site_1_der is not None
        assert isinstance(site_1_der, SiteDER)

        site_1_der.site_der_availability = clone_class_instance(
            der_avail, ignored_properties=set(["site_der_availability_id"])
        )
        site_1_der.site_der_rating = clone_class_instance(der_rating, ignored_properties=set(["site_der_rating_id"]))
        site_1_der.site_der_setting = clone_class_instance(der_setting, ignored_properties=set(["site_der_setting_id"]))
        site_1_der.site_der_status = clone_class_instance(der_status, ignored_properties=set(["site_der_status_id"]))
        await session.commit()

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

        assert_class_instance_equality(
            SiteDERAvailability,
            der_avail,
            site_1_der.site_der_availability,
            ignored_properties=set(["site_der_availability_id"]),
        )

        assert_class_instance_equality(
            SiteDERRating,
            der_rating,
            site_1_der.site_der_rating,
            ignored_properties=set(["site_der_rating_id"]),
        )

        assert_class_instance_equality(
            SiteDERSetting,
            der_setting,
            site_1_der.site_der_setting,
            ignored_properties=set(["site_der_setting_id"]),
        )

        assert_class_instance_equality(
            SiteDERStatus,
            der_status,
            site_1_der.site_der_status,
            ignored_properties=set(["site_der_status_id"]),
        )

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
