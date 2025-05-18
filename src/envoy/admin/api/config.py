import logging
from http import HTTPStatus

from envoy_schema.admin.schema.config import (
    ControlDefaultRequest,
    ControlDefaultResponse,
    RuntimeServerConfigRequest,
    RuntimeServerConfigResponse,
)
from envoy_schema.admin.schema.uri import ServerConfigRuntimeUri, SiteControlDefaultConfigUri
from fastapi import APIRouter
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.config import ConfigManager
from envoy.server.api.error_handler import LoggedHttpException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(ServerConfigRuntimeUri, status_code=HTTPStatus.NO_CONTENT, response_model=None)
async def update_runtime_config(body: RuntimeServerConfigRequest) -> None:
    """Updates the runtime config. Any missing values will NOT be updated.

    Body:
        single RuntimeServerConfigRequest object.

    Returns:
        None
    """
    await ConfigManager.update_current_config(db.session, body)


@router.get(ServerConfigRuntimeUri, status_code=HTTPStatus.OK, response_model=RuntimeServerConfigResponse)
async def get_runtime_config() -> RuntimeServerConfigResponse:
    """Fetches the current runtime config

    Returns:
        RuntimeServerConfigResponse
    """
    return await ConfigManager.fetch_config_response(db.session)


@router.post(SiteControlDefaultConfigUri, status_code=HTTPStatus.NO_CONTENT, response_model=None)
async def update_site_control_default(site_id: int, body: ControlDefaultRequest) -> None:
    """Updates the control default config for the specified site. Any missing values will NOT be updated.

    Body:
        single ControlDefaultRequest object.

    Returns:
        None
    """
    result = await ConfigManager.update_site_control_default(db.session, site_id, body)
    if not result:
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"site_id {site_id} not found")


@router.get(SiteControlDefaultConfigUri, status_code=HTTPStatus.OK, response_model=ControlDefaultResponse)
async def get_site_control_default(site_id: int) -> ControlDefaultResponse:
    """Gets the control default config for the specified site.

    Returns:
        ControlDefaultResponse or 404
    """
    result = await ConfigManager.fetch_site_control_default_response(db.session, site_id)
    if not result:
        raise LoggedHttpException(logger, None, HTTPStatus.NOT_FOUND, f"site_id {site_id} not found")
    return result
