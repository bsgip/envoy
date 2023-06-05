import pytest

from envoy.admin.crud.doe import insert_single_doe, select_single_doe
from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdminRequest, DynamicOperatingEnvelopeAdminResponse
from envoy.server.model.doe import DynamicOperatingEnvelope
from tests.data.fake.generator import generate_class_instance
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_insert_single_doe(pg_empty_config):
    """Assert that we are able to successfully insert a valid DOERequest into a db"""

    async with generate_async_session(pg_empty_config) as session:
        doe_in: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope)

        doe_in.dynamic_operating_envelope_id = None
        doe_in.site_id = 1

        await insert_single_doe(session, doe_in)
        await session.flush()

        assert doe_in.dynamic_operating_envelope_id == 1


# async def test_update_single_doe():
#     pass


# async def test_get_single_doe_by_id():
#     pass
