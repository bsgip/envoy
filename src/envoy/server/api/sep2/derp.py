import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi_async_sqlalchemy import db
from sqlalchemy.exc import NoResultFound

from envoy.server.api.request import (
    extract_aggregator_id,
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_start_from_paging_param,
)
from envoy.server.api.response import XmlResponse
from envoy.server.manager.derp import DERControlManager, DERProgramManager
from envoy.server.manager.pricing import RateComponentManager
from envoy.server.mapper.exception import InvalidMappingError

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
    try:
        derp_list = await DERProgramManager.fetch_list_for_site(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            site_id=site_id,
        )
    except InvalidMappingError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NoResultFound:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derp_list)


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
    try:
        derp = await DERProgramManager.fetch_doe_program_for_site(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            site_id=site_id,
        )
    except InvalidMappingError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NoResultFound:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derp)


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
    try:
        derc_list = await DERControlManager.fetch_doe_controls_for_site(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            site_id=site_id,
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit)
        )
    except InvalidMappingError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NoResultFound:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derc_list)


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
    try:
        derc_list = await DERControlManager.fetch_doe_controls_for_site_day(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            site_id=site_id,
            day=RateComponentManager.parse_rate_component_id(date),
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit)
        )
    except InvalidMappingError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NoResultFound:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(derc_list)