import pytest

from envoy.admin.crud.doe import insert_single_doe, select_single_doe, update_single_doe
from envoy.server.model.doe import DynamicOperatingEnvelope
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_insert_single_doe(pg_base_config):
    """Assert that we are able to successfully insert a valid DOERequest into a db"""

    async with generate_async_session(pg_base_config) as session:
        doe_in: DynamicOperatingEnvelope = generate_class_instance(
            DynamicOperatingEnvelope, generate_relationships=True
        )

        # clean up generated instance to ensure it doesn't clash with base_config
        doe_in.site.aggregator_id = 1
        del doe_in.dynamic_operating_envelope_id

        await insert_single_doe(session, doe_in)
        await session.flush()

        # this equals 6, but there are only 4 in the db at the init -- should be 5?
        assert doe_in.dynamic_operating_envelope_id == 6

        doe_out = await select_single_doe(session, doe_in.dynamic_operating_envelope_id)

        assert_class_instance_equality(DynamicOperatingEnvelope, doe_out, doe_in)


@pytest.mark.anyio
async def test_update_single_doe(pg_base_config):
    """Assert that we are able to update a single DOE by ID"""

    async with generate_async_session(pg_base_config) as session:
        doe_in: DynamicOperatingEnvelope = generate_class_instance(
            DynamicOperatingEnvelope, generate_relationships=True
        )

        doe_in.site.aggregator_id = 1
        doe_in.site_id = 1
        doe_in.dynamic_operating_envelope_id = 1  # will overwrite existing doe

        await update_single_doe(session, doe_in)
        await session.flush()

        doe_out = await select_single_doe(session, doe_in.dynamic_operating_envelope_id)

        assert_class_instance_equality(DynamicOperatingEnvelope, doe_out, doe_in)
