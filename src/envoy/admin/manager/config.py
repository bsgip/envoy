from datetime import datetime, timezone

from envoy_schema.admin.schema.config import RuntimeServerConfigRequest, RuntimeServerConfigResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.server import select_server_config
from envoy.server.manager.server import _map_server_config
from envoy.server.manager.time import utc_now
from envoy.server.model.server import RuntimeServerConfig as ConfigEntity
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

        changed_fsal_pollrate = False
        changed_edevl_pollrate = False

        if updated_values.dcap_pollrate_seconds is not None:
            existing_db_config.dcap_pollrate_seconds = updated_values.dcap_pollrate_seconds

        if updated_values.edevl_pollrate_seconds is not None:
            changed_edevl_pollrate = existing_db_config.edevl_pollrate_seconds != updated_values.edevl_pollrate_seconds
            existing_db_config.edevl_pollrate_seconds = updated_values.edevl_pollrate_seconds

        if updated_values.fsal_pollrate_seconds is not None:
            changed_fsal_pollrate = existing_db_config.fsal_pollrate_seconds != updated_values.fsal_pollrate_seconds
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

        if changed_fsal_pollrate:
            await NotificationManager.notify_changed_deleted_entities(
                SubscriptionResource.FUNCTION_SET_ASSIGNMENTS, now
            )

        if changed_edevl_pollrate:
            await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.SITE, now)

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
