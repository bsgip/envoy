import logging
from http import HTTPStatus

from envoy_schema.admin.schema.config import RuntimeServerConfigRequest, RuntimeServerConfigResponse
from envoy_schema.admin.schema.uri import ServerConfigRuntimeUri
from fastapi import APIRouter
from fastapi_async_sqlalchemy import db

from envoy.admin.manager.config import ConfigManager

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
