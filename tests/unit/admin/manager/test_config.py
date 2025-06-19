from decimal import Decimal

import pytest
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.config import ControlDefaultRequest, UpdateDefaultValue
from sqlalchemy import select

from envoy.admin.manager.config import ConfigManager
from envoy.server.model.site import DefaultSiteControl


@pytest.mark.parametrize(
    "site_id, control_request",
    [
        (
            1,
            ControlDefaultRequest(
                import_limit_watts=UpdateDefaultValue(value=None),
                export_limit_watts=UpdateDefaultValue(value=None),
                load_limit_watts=UpdateDefaultValue(value=None),
                generation_limit_watts=UpdateDefaultValue(value=None),
                ramp_rate_percent_per_second=UpdateDefaultValue(value=None),
            ),
        ),
        (
            3,
            ControlDefaultRequest(
                import_limit_watts=UpdateDefaultValue(value=Decimal(11)),
                export_limit_watts=UpdateDefaultValue(value=Decimal(12)),
                load_limit_watts=UpdateDefaultValue(value=Decimal(13)),
                generation_limit_watts=UpdateDefaultValue(value=Decimal(14)),
                ramp_rate_percent_per_second=UpdateDefaultValue(value=Decimal(15)),
            ),
        ),
    ],
)
@pytest.mark.anyio
async def test_update_site_control_default_all_vals_update(
    pg_base_config, site_id: int, control_request: ControlDefaultRequest
):
    """Tests that the values for existing/new control defaults can be correctly updated"""
    async with generate_async_session(pg_base_config) as session:
        await ConfigManager.update_site_control_default(session, site_id, control_request)

    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        result = await session.execute(select(DefaultSiteControl).where(DefaultSiteControl.site_id == site_id))
        saved_result = result.scalar_one()
        assert saved_result.import_limit_active_watts == control_request.import_limit_watts.value
        assert saved_result.export_limit_active_watts == control_request.export_limit_watts.value
        assert saved_result.generation_limit_active_watts == control_request.generation_limit_watts.value
        assert saved_result.load_limit_active_watts == control_request.load_limit_watts.value
        assert saved_result.ramp_rate_percent_per_second == control_request.ramp_rate_percent_per_second.value
