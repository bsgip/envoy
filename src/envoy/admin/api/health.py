import logging
from http import HTTPStatus

from fastapi import APIRouter, Response
from fastapi_async_sqlalchemy import db

from envoy.server.manager.health import HealthManager

logger = logging.getLogger(__name__)


router = APIRouter()

HEALTH_URI = "/status/health"


@router.head(HEALTH_URI)
@router.get(HEALTH_URI, status_code=HTTPStatus.OK)
async def get_health(check_data: bool = True) -> Response:
    """Responds with a HTTP 200 if the server diagnostics report everything is OK. HTTP 500 otherwise.

    Response will be a plaintext encoding of the passing/failing health checks

    Returns:
        fastapi.Response object.
    """

    check = await HealthManager.run_health_check(db.session)
    headers = {"Content-Type": "text/plain"}
    content = str(check)

    if not check.database_connectivity:
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    elif check_data and not check.database_has_data:
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    else:
        status_code = HTTPStatus.OK

    return Response(content=content, status_code=status_code, headers=headers)
