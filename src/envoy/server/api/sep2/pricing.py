import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from fastapi import APIRouter, Query, Request
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_request_claims,
    extract_start_from_paging_param,
)
from envoy.server.api.response import XmlResponse
from envoy.server.exception import NotFoundError
from envoy.server.manager.pricing import (
    ConsumptionTariffIntervalManager,
    RateComponentManager,
    TariffProfileManager,
    TimeTariffIntervalManager,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head(uri.PricingReadingTypeUri)
@router.get(uri.PricingReadingTypeUri, status_code=HTTPStatus.OK)
async def get_pricingreadingtype(request: Request, site_id: int, tariff_id: int, rate_component_id: int) -> XmlResponse:
    """Responds with ReadingType describing the priced type of reading. This is to handle the ReadingType link
    referenced href callback from RateComponent.ReadingTypeLink.

    Responses will be static

    Returns:
        fastapi.Response object.
    """
    try:
        rt = RateComponentManager.fetch_reading_type(
            db.session,
            extract_request_claims(request).to_site_request_scope(site_id),
            tariff_id=tariff_id,
            rate_component_id=rate_component_id,
        )
        return XmlResponse(rt)
    except NotFoundError as exc:
        raise LoggedHttpException(logger, exc, status_code=HTTPStatus.NOT_FOUND, detail=exc.message)


@router.head(uri.TariffProfileFSAListUri)
@router.get(uri.TariffProfileFSAListUri, status_code=HTTPStatus.OK)
async def get_tariffprofilelist_fsa_scoped(
    request: Request,
    site_id: int,
    fsa_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of tariff profiles available to the current client. These tariffs
    will be scoped specifically to the specified site_id and function set assignment id

    Args:
        site_id: Path parameter - the site that the underlying tariffs will be scoped to
        fsa_id: Path parameter - the function set assignment ID tariffs will be scoped to
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """

    tp_list = await TariffProfileManager.fetch_tariff_profile_list(
        db.session,
        scope=extract_request_claims(request).to_site_request_scope(site_id),
        start=extract_start_from_paging_param(start),
        changed_after=extract_datetime_from_paging_param(after),
        limit=extract_limit_from_paging_param(limit),
        fsa_id=fsa_id,
    )

    return XmlResponse(tp_list)


@router.head(uri.TariffProfileUri)
@router.get(uri.TariffProfileUri, status_code=HTTPStatus.OK)
async def get_singletariffprofile(tariff_id: int, site_id: int, request: Request) -> XmlResponse:
    """Responds with a single TariffProfile resource identified by tariff_id for a specific site id.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the underlying rates will be scoped to
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """

    tp = await TariffProfileManager.fetch_tariff_profile(
        db.session, extract_request_claims(request).to_site_request_scope(site_id), tariff_id
    )
    if tp is None:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(tp)


@router.head(uri.RateComponentListUri)
@router.get(uri.RateComponentListUri, status_code=HTTPStatus.OK)
async def get_ratecomponentlist(
    tariff_id: int,
    site_id: int,
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of RateComponents belonging to tariff_id/site_id.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    rc_list = await RateComponentManager.fetch_rate_component_list(
        db.session,
        scope=extract_request_claims(request).to_site_request_scope(site_id),
        tariff_id=tariff_id,
        start=extract_start_from_paging_param(start),
        changed_after=extract_datetime_from_paging_param(after),
        limit=extract_limit_from_paging_param(limit),
    )
    return XmlResponse(rc_list)


@router.head(uri.RateComponentUri)
@router.get(uri.RateComponentUri, status_code=HTTPStatus.OK)
async def get_singleratecomponent(
    tariff_id: int, site_id: int, rate_component_id: int, request: Request
) -> XmlResponse:
    """Responds with a single RateComponent resource identified by the parent tariff_id and target rate_component_id.


    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter, the target RateComponent id
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    rc = await RateComponentManager.fetch_rate_component(
        db.session,
        scope=extract_request_claims(request).to_site_request_scope(site_id),
        tariff_id=tariff_id,
        rate_component_id=rate_component_id,
    )
    if rc is None:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(rc)


@router.head(uri.CombinedTimeTariffIntervalListUri)
@router.get(uri.CombinedTimeTariffIntervalListUri, status_code=HTTPStatus.OK)
async def get_combinedtimetariffintervallist(
    tariff_id: int,
    site_id: int,
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of TimeTariffInterval entities belonging to the specified tariff across all
    RateComponents.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        tti_list = await TimeTariffIntervalManager.fetch_combined_time_tariff_interval_list(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            tariff_id=tariff_id,
            start=extract_start_from_paging_param(start),
            after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(tti_list)


@router.head(uri.TimeTariffIntervalListUri)
@router.get(uri.TimeTariffIntervalListUri, status_code=HTTPStatus.OK)
async def get_timetariffintervallist(
    tariff_id: int,
    site_id: int,
    rate_component_id: int,
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of TimeTariffInterval entities belonging to the specified tariff/rate_component.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter - the target RateComponent id
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        tti_list = await TimeTariffIntervalManager.fetch_time_tariff_interval_list(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            tariff_id=tariff_id,
            rate_component_id=rate_component_id,
            start=extract_start_from_paging_param(start),
            after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except NotFoundError as ex:
        raise LoggedHttpException(logger, ex, status_code=HTTPStatus.NOT_FOUND, detail=ex.message)

    return XmlResponse(tti_list)


@router.head(uri.TimeTariffIntervalUri)
@router.get(uri.TimeTariffIntervalUri, status_code=HTTPStatus.OK)
async def get_singletimetariffinterval(
    tariff_id: int,
    site_id: int,
    rate_component_id: int,
    tti_id: int,
    request: Request,
) -> XmlResponse:
    """Responds with a single TimeTariffInterval resource identified by the set of ID's.


    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter, the target RateComponent id
        tti_id: Path parameter, the target TimeTariffInterval id
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    tti = await TimeTariffIntervalManager.fetch_time_tariff_interval(
        db.session,
        scope=extract_request_claims(request).to_site_request_scope(site_id),
        tariff_id=tariff_id,
        rate_component_id=rate_component_id,
        time_tariff_interval_id=tti_id,
    )

    if tti is None:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(tti)


@router.head(uri.ConsumptionTariffIntervalListUri)
@router.get(uri.ConsumptionTariffIntervalListUri, status_code=HTTPStatus.OK)
async def get_consumptiontariffintervallist(
    tariff_id: int,
    site_id: int,
    rate_component_id: int,
    tti_id: int,
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of ConsumptionTariffInterval belonging to specified parent ids.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter, the target RateComponent id
        tti_id: Path parameter, the target TimeTariffInterval id
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        cti_list = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval_list(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            tariff_id=tariff_id,
            rate_component_id=rate_component_id,
            time_tariff_interval_id=tti_id,
        )
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(cti_list)


@router.head(uri.ConsumptionTariffIntervalUri)
@router.get(uri.ConsumptionTariffIntervalUri, status_code=HTTPStatus.OK)
async def get_singleconsumptiontariffinterval(
    tariff_id: int,
    site_id: int,
    rate_component_id: int,
    tti_id: int,
    cti_id: int,
    request: Request,
) -> XmlResponse:
    """Responds with a single ConsumptionTariffInterval resource.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter, the target RateComponent id
        pricing_reading: Path parameter - the specific type of readings the prices should be associated with
        tti_id: Path parameter, the target TimeTariffInterval id
        cti_id: Path parameter, the target ConsumptionTariffInterval id
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """

    try:
        cti = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval(
            db.session,
            scope=extract_request_claims(request).to_site_request_scope(site_id),
            tariff_id=tariff_id,
            rate_component_id=rate_component_id,
            time_tariff_interval_id=tti_id,
            consumption_tariff_interval_id=cti_id,
        )
    except NotFoundError:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not found.")

    return XmlResponse(cti)
