from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from envoy_schema.admin.schema.config import (
    ControlDefaultRequest,
    ControlDefaultResponse,
    RuntimeServerConfigRequest,
    RuntimeServerConfigResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.site import select_single_site_no_scoping
from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.server import select_server_config
from envoy.server.manager.server import _map_server_config
from envoy.server.manager.time import utc_now
from envoy.server.model.server import RuntimeServerConfig as ConfigEntity
from envoy.server.model.site import DefaultSiteControl
from envoy.server.model.subscription import SubscriptionResource


class ConfigManager:

    @staticmethod
    async def update_current_config(session: AsyncSession, updated_values: RuntimeServerConfigRequest) -> None:
        """Applies updated_values to the current server configuration. Will only set the non None values"""
        now = utc_now()
        existing_db_config = await select_server_config(session)

        if existing_db_config is None:
            # if this is our first DB entry - create it and add it to the session
            existing_db_config = ConfigEntity(changed_time=now)
            session.add(existing_db_config)
        else:
            existing_db_config.changed_time = now

        if updated_values.dcap_pollrate_seconds is not None:
            existing_db_config.dcap_pollrate_seconds = updated_values.dcap_pollrate_seconds

        if updated_values.edevl_pollrate_seconds is not None:
            existing_db_config.edevl_pollrate_seconds = updated_values.edevl_pollrate_seconds

        if updated_values.fsal_pollrate_seconds is not None:
            existing_db_config.fsal_pollrate_seconds = updated_values.fsal_pollrate_seconds

        if updated_values.derpl_pollrate_seconds is not None:
            existing_db_config.derpl_pollrate_seconds = updated_values.derpl_pollrate_seconds

        if updated_values.derl_pollrate_seconds is not None:
            existing_db_config.derl_pollrate_seconds = updated_values.derl_pollrate_seconds

        if updated_values.mup_postrate_seconds is not None:
            existing_db_config.mup_postrate_seconds = updated_values.mup_postrate_seconds

        if updated_values.site_control_pow10_encoding is not None:
            existing_db_config.site_control_pow10_encoding = updated_values.site_control_pow10_encoding

        if updated_values.disable_edev_registration is not None:
            existing_db_config.disable_edev_registration = updated_values.disable_edev_registration

        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.FUNCTION_SET_ASSIGNMENTS, now)

    @staticmethod
    async def fetch_config_response(session: AsyncSession) -> RuntimeServerConfigResponse:
        """Fetches the current configuration values as a RuntimeServerConfigResponse for external communication"""
        existing = await select_server_config(session)
        if existing:
            changed_time = existing.changed_time
            created_time = existing.created_time
        else:
            changed_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
            created_time = changed_time

        config = _map_server_config(existing)

        return RuntimeServerConfigResponse(
            dcap_pollrate_seconds=config.dcap_pollrate_seconds,
            edevl_pollrate_seconds=config.edevl_pollrate_seconds,
            fsal_pollrate_seconds=config.fsal_pollrate_seconds,
            derl_pollrate_seconds=config.derl_pollrate_seconds,
            derpl_pollrate_seconds=config.derpl_pollrate_seconds,
            mup_postrate_seconds=config.mup_postrate_seconds,
            site_control_pow10_encoding=config.site_control_pow10_encoding,
            disable_edev_registration=config.disable_edev_registration,
            tariff_pow10_encoding=-4,  # Currently held constant
            changed_time=changed_time,
            created_time=created_time,
        )

    @staticmethod
    async def update_site_control_default(session: AsyncSession, site_id: int, request: ControlDefaultRequest) -> bool:
        now = utc_now()

        site = await select_single_site_no_scoping(session, site_id, include_site_default=True)
        if site is None:
            return False

        if site.default_site_control is None:
            site.default_site_control = DefaultSiteControl(changed_time=now, site_id=site.site_id)
        else:
            site.default_site_control.changed_time = now

        if request.import_limit_watts is not None:
            site.default_site_control.import_limit_active_watts = request.import_limit_watts.value

        if request.export_limit_watts is not None:
            site.default_site_control.export_limit_active_watts = request.export_limit_watts.value

        if request.generation_limit_watts is not None:
            site.default_site_control.generation_limit_active_watts = request.generation_limit_watts.value

        if request.load_limit_watts is not None:
            site.default_site_control.load_limit_active_watts = request.load_limit_watts.value

        if request.ramp_rate_percent_per_second is not None:
            ramp_rate_value = (
                int(request.ramp_rate_percent_per_second.value)
                if request.ramp_rate_percent_per_second.value is not None
                else None
            )
            site.default_site_control.ramp_rate_percent_per_second = ramp_rate_value

        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.DEFAULT_SITE_CONTROL, now)

        return True

    @staticmethod
    async def fetch_site_control_default_response(
        session: AsyncSession, site_id: int
    ) -> Optional[ControlDefaultResponse]:
        """Fetches the current site control default values as a ControlDefaultResponse for external communication"""
        site = await select_single_site_no_scoping(session, site_id, include_site_default=True)
        if not site:
            return None
        if site.default_site_control:
            default_config = site.default_site_control
        else:
            default_config = DefaultSiteControl(
                changed_time=site.changed_time, created_time=site.created_time, site_id=site.site_id
            )

        return ControlDefaultResponse(
            ramp_rate_percent_per_second=(
                Decimal(default_config.ramp_rate_percent_per_second)
                if default_config.ramp_rate_percent_per_second is not None
                else None
            ),
            server_default_import_limit_watts=default_config.import_limit_active_watts,
            server_default_export_limit_watts=default_config.export_limit_active_watts,
            server_default_generation_limit_watts=default_config.generation_limit_active_watts,
            server_default_load_limit_watts=default_config.load_limit_active_watts,
            changed_time=default_config.changed_time,
            created_time=default_config.created_time,
        )
