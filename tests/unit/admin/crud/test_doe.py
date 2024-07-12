from datetime import timedelta

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import select

from envoy.admin.crud.doe import upsert_many_doe
from envoy.server.model.doe import DynamicOperatingEnvelope


async def _select_latest_dynamic_operating_envelope(session):
    stmt = (
        select(DynamicOperatingEnvelope)
        .order_by(DynamicOperatingEnvelope.dynamic_operating_envelope_id.desc())
        .limit(1)
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


@pytest.mark.anyio
async def test_upsert_many_doe(pg_base_config):
    """Assert that we are able to successfully insert a valid DOERequest into a db"""

    async with generate_async_session(pg_base_config) as session:
        doe_in: DynamicOperatingEnvelope = generate_class_instance(
            DynamicOperatingEnvelope, generate_relationships=False
        )

        # clean up generated instance to ensure it doesn't clash with base_config
        doe_in.site_id = 1
        del doe_in.dynamic_operating_envelope_id

        await upsert_many_doe(session, [doe_in])
        await session.flush()

        doe_out = await _select_latest_dynamic_operating_envelope(session)

        assert_class_instance_equality(
            DynamicOperatingEnvelope, doe_out, doe_in, ignored_properties={"dynamic_operating_envelope_id"}
        )

        doe_in_1 = generate_class_instance(DynamicOperatingEnvelope)
        doe_in_1.site_id = 1
        doe_in_1.start_time = doe_in.start_time + timedelta(seconds=1)

        await upsert_many_doe(session, [doe_in, doe_in_1])
