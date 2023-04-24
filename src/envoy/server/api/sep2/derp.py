import logging
from http import HTTPStatus

from fastapi import APIRouter, Query, Request
from fastapi_async_sqlalchemy import db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head("/derp/{site_id}")
@router.get("/derp/{site_id}", status_code=HTTPStatus.OK)
async def get_derprogram_list(request: Request,
                              site_id: int,
                              start: list[int] = Query([0], alias="s"),
                              after: list[int] = Query([0], alias="a"),
                              limit: list[int] = Query([1], alias="l")):
    """Responds with a single DERProgramListResponse containing DER programs for the specified site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    raise NotImplementedError()


@router.head("/derp/{site_id}/doe")
@router.get("/derp/{site_id}/doe", status_code=HTTPStatus.OK)
async def get_derprogram_doe(request: Request,
                             site_id: int):
    """Responds with a single DERProgramResponse for the DER Program specific to dynamic operating envelopes

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
    Returns:
        fastapi.Response object.
    """
    raise NotImplementedError()

@router.head("/derp/{site_id}/doe/derc")
@router.get("/derp/{site_id}/doe/derc", status_code=HTTPStatus.OK)
async def get_dercontrol_list(request: Request,
                              site_id: int,
                              start: list[int] = Query([0], alias="s"),
                              after: list[int] = Query([0], alias="a"),
                              limit: list[int] = Query([1], alias="l")):
    """Responds with a single DERControlListResponse containing DER Controls for the specified site under the
    dynamic operating envelope program.

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    raise NotImplementedError()


@router.head("/derp/{site_id}/doe/derc/{date}")
@router.get("/derp/{site_id}/doe/derc/{date}", status_code=HTTPStatus.OK)
async def get_dercontrol_list_for_date(request: Request,
                                       site_id: int,
                                       date: str,
                                       start: list[int] = Query([0], alias="s"),
                                       after: list[int] = Query([0], alias="a"),
                                       limit: list[int] = Query([1], alias="l")):
    """Responds with a single DERControlListResponse containing DER Controls for the specified site under the
    dynamic operating envelope program. Results will be filtered to the specified date

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        date: Path parameter, the YYYY-MM-DD in site local time that controls will be filtered to
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.
    """
    raise NotImplementedError()

