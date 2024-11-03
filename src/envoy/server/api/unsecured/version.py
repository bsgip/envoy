import logging
from http import HTTPStatus

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)


router = APIRouter()

VERSION_URI = "/status/version"


@router.head(VERSION_URI)
@router.get(VERSION_URI, status_code=HTTPStatus.OK)
async def get_version(request: Request) -> Response:
    """Responds with a plaintext printout of the current envoy version. Eg: 1.2.3

    Returns:
        fastapi.Response object.
    """

    headers = {"Content-Type": "text/plain"}
    content = str(getattr(request.app, "version", "Unknown"))

    return Response(content=content, status_code=HTTPStatus.OK, headers=headers)
