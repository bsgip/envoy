from datetime import datetime, timezone
from typing import Optional

import pytest
from envoy_schema.server.schema.sep2.der import DERAvailability, DERCapability, DERControlType, DERSettings, DERStatus
from sqlalchemy import func, select

from envoy.server.crud.der import generate_default_site_der, select_site_der_for_site
from envoy.server.exception import NotFoundError
from envoy.server.manager.der import PUBLIC_SITE_DER_ID, DERCapabilityManager
from envoy.server.mapper.sep2.der import DERCapabilityMapper, to_hex_binary
from envoy.server.model.site import SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.request_state import RequestStateParameters
from tests.assert_time import assert_datetime_equal
from tests.data.fake.generator import assert_class_instance_equality, clone_class_instance, generate_class_instance
from tests.postgres_testing import generate_async_session


@pytest.mark.parametrize(
    "agg_id, site_id, der_id",
    [
        (99, 1, PUBLIC_SITE_DER_ID),  # invalid agg_id
        (2, 1, PUBLIC_SITE_DER_ID),  # Invalid agg_id
        (1, 99, PUBLIC_SITE_DER_ID),  # Invalid site id
        (1, 1, PUBLIC_SITE_DER_ID + 1),  # invalid DER id
    ],
)
@pytest.mark.anyio
async def test_upsert_der_capability_not_found(pg_base_config, agg_id: int, site_id: int, der_id: int):
    """Tests the various ways a NotFoundError can be raised"""
    rs_params = RequestStateParameters(agg_id, None)

    async with generate_async_session(pg_base_config) as session:
        e: DERCapability = generate_class_instance(DERCapability, generate_relationships=True)
        e.modesSupported = to_hex_binary(DERControlType.OP_MOD_CONNECT)

        with pytest.raises(NotFoundError):
            await DERCapabilityManager.upsert_der_capability_for_site(
                session,
                site_id,
                der_id,
                rs_params,
                e,
            )

    # Validate we haven't added any rows on accident
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(func.count()).select_from(SiteDERRating))
        assert resp.scalar_one() == 0


@pytest.mark.parametrize(
    "agg_id, site_id, der_id",
    [
        (99, 1, PUBLIC_SITE_DER_ID),  # invalid agg_id
        (2, 1, PUBLIC_SITE_DER_ID),  # Invalid agg_id
        (1, 99, PUBLIC_SITE_DER_ID),  # Invalid site id
        (1, 1, PUBLIC_SITE_DER_ID + 1),  # invalid DER id
        (1, 1, PUBLIC_SITE_DER_ID),  # There is no entity record in the db
        (1, 4, PUBLIC_SITE_DER_ID),  # There is DER or entity record in the db
    ],
)
@pytest.mark.anyio
async def test_fetch_der_capability_not_found(pg_base_config, agg_id: int, site_id: int, der_id: int):
    """Tests the various ways a NotFoundError can be raised"""
    rs_params = RequestStateParameters(agg_id, None)

    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(NotFoundError):
            await DERCapabilityManager.fetch_der_capability_for_site(
                session,
                site_id,
                der_id,
                rs_params,
            )


@pytest.mark.parametrize(
    "site_id, update_site_der_id",
    [
        (1, None),  # Existing DER - insert record
        (1, 2),  # Existing DER - update record
        (4, None),  # Missing DER - insert both
    ],
)
@pytest.mark.anyio
async def test_upsert_der_capability_roundtrip(pg_base_config, site_id: int, update_site_der_id: Optional[int]):
    """Tests the various success paths through updating"""
    agg_id = 1
    rs_params = RequestStateParameters(agg_id, "/custom/prefix")

    # If set - insert a new entity that will be forced to update
    if update_site_der_id is not None:
        async with generate_async_session(pg_base_config) as session:
            updated_entity: SiteDERRating = generate_class_instance(SiteDERRating, seed=1001)
            updated_entity.site_der_id = update_site_der_id
            session.add(updated_entity)
            await session.commit()

    # Do the upsert
    expected: DERCapability = generate_class_instance(DERCapability, seed=22, generate_relationships=True)
    expected.modesSupported = to_hex_binary(
        DERControlType.OP_MOD_HVRT_MUST_TRIP | DERControlType.OP_MOD_HVRT_MOMENTARY_CESSATION
    )
    async with generate_async_session(pg_base_config) as session:
        await DERCapabilityManager.upsert_der_capability_for_site(
            session,
            site_id,
            PUBLIC_SITE_DER_ID,
            rs_params,
            clone_class_instance(expected),
        )

    # Use a new session to query everything back
    async with generate_async_session(pg_base_config) as session:
        actual = await DERCapabilityManager.fetch_der_capability_for_site(
            session, site_id, PUBLIC_SITE_DER_ID, rs_params
        )

        assert_class_instance_equality(
            DERCapability,
            expected,
            actual,
            ignored_properties=set(["href", "subscribable", "type"]),
        )
        assert actual.href.startswith(rs_params.href_prefix)
        assert str(site_id) in actual.href

    # Validate we haven't added multiple rows on accident
    async with generate_async_session(pg_base_config) as session:
        resp = await session.execute(select(func.count()).select_from(SiteDERRating))
        assert resp.scalar_one() == 1
