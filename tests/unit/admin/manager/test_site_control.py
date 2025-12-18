import unittest.mock as mock
from decimal import Decimal

import pytest
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.site_control import SiteControlGroupDefaultRequest, UpdateDefaultValue
from sqlalchemy import func, select

from envoy.admin.manager.site_control import SiteControlGroupManager
from envoy.server.model.archive.doe import ArchiveSiteControlGroupDefault
from envoy.server.model.doe import SiteControlGroupDefault


@pytest.mark.parametrize(
    "group_id, control_request",
    [
        (
            1,
            SiteControlGroupDefaultRequest(
                import_limit_watts=UpdateDefaultValue(value=None),
                export_limit_watts=UpdateDefaultValue(value=None),
                load_limit_watts=UpdateDefaultValue(value=None),
                generation_limit_watts=UpdateDefaultValue(value=None),
                ramp_rate_percent_per_second=UpdateDefaultValue(value=None),
            ),
        ),
        (
            1,
            SiteControlGroupDefaultRequest(
                import_limit_watts=UpdateDefaultValue(value=Decimal(11)),
                export_limit_watts=UpdateDefaultValue(value=Decimal(12)),
                load_limit_watts=UpdateDefaultValue(value=Decimal(13)),
                generation_limit_watts=UpdateDefaultValue(value=Decimal(14)),
                ramp_rate_percent_per_second=UpdateDefaultValue(value=Decimal(15)),
            ),
        ),
        (
            2,
            SiteControlGroupDefaultRequest(
                import_limit_watts=UpdateDefaultValue(value=Decimal(11)),
                export_limit_watts=UpdateDefaultValue(value=Decimal(12)),
                load_limit_watts=UpdateDefaultValue(value=Decimal(13)),
                generation_limit_watts=UpdateDefaultValue(value=Decimal(14)),
                ramp_rate_percent_per_second=UpdateDefaultValue(value=Decimal(15)),
            ),
        ),
        (
            3,
            SiteControlGroupDefaultRequest(
                import_limit_watts=UpdateDefaultValue(value=Decimal(11)),
                export_limit_watts=UpdateDefaultValue(value=Decimal(12)),
                load_limit_watts=UpdateDefaultValue(value=Decimal(13)),
                generation_limit_watts=UpdateDefaultValue(value=Decimal(14)),
                ramp_rate_percent_per_second=UpdateDefaultValue(value=Decimal(15)),
            ),
        ),
    ],
)
@mock.patch("envoy.admin.manager.config.NotificationManager.notify_changed_deleted_entities")
@pytest.mark.anyio
async def test_update_site_control_default_all_vals_update(
    mock_notify_changed_deleted_entities: mock.MagicMock,
    pg_base_config,
    group_id: int,
    control_request: SiteControlGroupDefaultRequest,
):
    """Tests that the values for existing/new control defaults can be correctly updated"""
    async with generate_async_session(pg_base_config) as session:
        version_before = (
            await session.execute(
                select(SiteControlGroupDefault.version).where(SiteControlGroupDefault.site_control_group_id == group_id)
            )
        ).scalar_one_or_none()

    async with generate_async_session(pg_base_config) as session:
        await SiteControlGroupManager.update_site_control_default(session, group_id, control_request)

    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        result = await session.execute(
            select(SiteControlGroupDefault).where(SiteControlGroupDefault.site_control_group_id == group_id)
        )
        saved_result = result.scalar_one()
        assert saved_result.import_limit_active_watts == control_request.import_limit_watts.value
        assert saved_result.export_limit_active_watts == control_request.export_limit_watts.value
        assert saved_result.generation_limit_active_watts == control_request.generation_limit_watts.value
        assert saved_result.load_limit_active_watts == control_request.load_limit_watts.value
        assert saved_result.ramp_rate_percent_per_second == control_request.ramp_rate_percent_per_second.value

        if version_before is None:
            assert saved_result.version == 1
            assert (
                await session.execute(select(func.count()).select_from(ArchiveSiteControlGroupDefault))
            ).scalar_one() == 0, "No archive rows if this is a new default"
        else:
            assert saved_result.version == version_before + 1, "This should be incremented as part of the update"
            assert (
                await session.execute(select(func.count()).select_from(ArchiveSiteControlGroupDefault))
            ).scalar_one() == 1, "Old values should've been archived"

    mock_notify_changed_deleted_entities.assert_called_once()
