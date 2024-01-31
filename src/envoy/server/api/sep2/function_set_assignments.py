import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from fastapi import APIRouter, Request
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import NoResultFound

from envoy.server.api import query
from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import extract_request_params
from envoy.server.api.response import XmlResponse
from envoy.server.manager.function_set_assignments import FunctionSetAssignmentsManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head(uri.FunctionSetAssignmentsUri)
@router.get(
    uri.FunctionSetAssignmentsUri,
    status_code=HTTPStatus.OK,
)
async def get_function_set_assignments(site_id: int, fsa_id: int, request: Request) -> XmlResponse:
    """Responds with a single FunctionSetAssignments for a requested site.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        fsa_id: Path parameter, the target FunctionSetAssignments internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.
    """
    try:
        function_set_assignments = (
            await FunctionSetAssignmentsManager.fetch_function_set_assignments_for_aggregator_and_site(
                session=db.session, request_params=extract_request_params(request), site_id=site_id, fsa_id=fsa_id
            )
        )
    except NoResultFound as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")

    if function_set_assignments is None:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(function_set_assignments)


@router.head(uri.FunctionSetAssignmentsListUri)
@router.get(
    uri.FunctionSetAssignmentsListUri,
    status_code=HTTPStatus.OK,
)
async def get_function_set_assignments_list(
    site_id: int,
    request: Request,
    start: list[int] = query.StartQueryParameter,
    limit: list[int] = query.LimitQueryParameter,
) -> XmlResponse:
    """Responds with a FunctionSetAssignmentsList resource.

    Args:
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """

    # This function accepts the start and limit query parameters because it is a GET request for a List response
    # however FunctionSetAssignment will only ever return 1 FunctionSetAssignment per site so we ignore `start`
    # `limit`.

    function_set_assignments_list = (
        await FunctionSetAssignmentsManager.fetch_function_set_assignments_list_for_aggregator_and_site(
            session=db.session,
            site_id=site_id,
            request_params=extract_request_params(request),
        )
    )
    return XmlResponse(function_set_assignments_list)
