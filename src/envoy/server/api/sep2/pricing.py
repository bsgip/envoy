import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.pricing import RateComponentListResponse
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi_async_sqlalchemy import db

from envoy.server.api.request import (
    extract_aggregator_id,
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_start_from_paging_param,
)
from envoy.server.api.response import XmlResponse
from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.pricing import (
    ConsumptionTariffIntervalManager,
    RateComponentManager,
    TariffProfileManager,
    TimeTariffIntervalManager,
)
from envoy.server.mapper.sep2.pricing import PricingReadingType, PricingReadingTypeMapper

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head(uri.PricingReadingTypeUri)
@router.get(uri.PricingReadingTypeUri, status_code=HTTPStatus.OK)
async def get_pricingreadingtype(reading_type: PricingReadingType) -> XmlResponse:
    """Responds with ReadingType describing the priced type of reading. This is to handle the ReadingType link
    referenced href callback from RateComponent.ReadingTypeLink.

    Responses will be static

    Returns:
        fastapi.Response object.
    """
    try:
        return XmlResponse(PricingReadingTypeMapper.create_reading_type(reading_type))
    except BadRequestError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"Unsupported reading_type {reading_type}")


@router.head(uri.TariffProfileListUnscopedUri)
@router.get(uri.TariffProfileListUnscopedUri, status_code=HTTPStatus.OK)
async def get_tariffprofilelist_nositescope(
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of tariff profiles available to the current client. These tariffs
    will not lead to any prices directly as prices are specific to site/end devices which can be
    discovered via function set assignments. This endpoint is purely for strict sep2 compliance

    Args:
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        tp_list = await TariffProfileManager.fetch_tariff_profile_list_no_site(
            db.session,
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    return XmlResponse(tp_list)


@router.head(uri.TariffProfileListUri)
@router.get(uri.TariffProfileListUri, status_code=HTTPStatus.OK)
async def get_tariffprofilelist(
    request: Request,
    site_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of tariff profiles available to the current client. These tariffs
    will be scoped specifically to the specified site_id

    Args:
        site_id: Path parameter - the site that the underlying rates will be scoped to
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """
    try:
        tp_list = await TariffProfileManager.fetch_tariff_profile_list(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            site_id=site_id,
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    return XmlResponse(tp_list)


@router.head(uri.TariffProfileUnscopedUri)
@router.get(uri.TariffProfileUnscopedUri, status_code=HTTPStatus.OK)
async def get_singletariffprofile_nositescope(tariff_id: int, request: Request) -> XmlResponse:
    """Responds with a single TariffProfile resource identified by tariff_id. These tariffs
    will not lead to any prices directly as prices are specific to site/end devices which can be
    discovered via function set assignments. This endpoint is purely for strict sep2 compliance

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        tp = await TariffProfileManager.fetch_tariff_profile_no_site(db.session, tariff_id)
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    if tp is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(tp)


@router.head(uri.RateComponentListUnscopedUri)
@router.get(uri.RateComponentListUnscopedUri, status_code=HTTPStatus.OK)
async def get_ratecomponentlist_nositescope(
    tariff_id: int,
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of RateComponents belonging to tariff_id. This will
    always be empty as all prices are site specific. This endpoint is purely for strict sep2 compliance.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        request: FastAPI request object.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.

    Returns:
        fastapi.Response object.

    """

    # return an empty list - clients will only discover this endpoint by querying for tariff profiles
    # directly. Tariff profiles need to be discovered via function set assignments and from there
    # they will directed to the appropriate endpoint describing site scoped rates
    return XmlResponse(RateComponentListResponse.validate({"all_": 0, "results": 0, "href": request.url.path}))


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
    try:
        tp = await TariffProfileManager.fetch_tariff_profile(
            db.session, extract_aggregator_id(request), tariff_id, site_id
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    if tp is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

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
    try:
        rc_list = await RateComponentManager.fetch_rate_component_list(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            tariff_id=tariff_id,
            site_id=site_id,
            start=extract_start_from_paging_param(start),
            changed_after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    return XmlResponse(rc_list)


@router.head(uri.RateComponentUri)
@router.get(uri.RateComponentUri, status_code=HTTPStatus.OK)
async def get_singleratecomponent(
    tariff_id: int, site_id: int, rate_component_id: str, pricing_reading: PricingReadingType, request: Request
) -> XmlResponse:
    """Responds with a single RateComponent resource identified by the parent tariff_id and target rate_component_id.


    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        pricing_reading: Path parameter - the specific type of readings the prices should be associated with
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        rc = await RateComponentManager.fetch_rate_component(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            tariff_id=tariff_id,
            site_id=site_id,
            rate_component_id=rate_component_id,
            pricing_type=pricing_reading,
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    if rc is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(rc)


@router.head(uri.TimeTariffIntervalListUri)
@router.get(uri.TimeTariffIntervalListUri, status_code=HTTPStatus.OK)
async def get_timetariffintervallist(
    tariff_id: int,
    site_id: int,
    rate_component_id: str,
    pricing_reading: PricingReadingType,
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of TimeTariffInterval entities belonging to the specified tariff/rate_component.

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter - the target RateComponent id (should be a date in YYYY-MM-DD format)
        pricing_reading: Path parameter - the specific type of readings the prices should be associated with
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
            aggregator_id=extract_aggregator_id(request),
            tariff_id=tariff_id,
            site_id=site_id,
            rate_component_id=rate_component_id,
            pricing_type=pricing_reading,
            start=extract_start_from_paging_param(start),
            after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    return XmlResponse(tti_list)


@router.head(uri.TimeTariffIntervalUri)
@router.get(uri.TimeTariffIntervalUri, status_code=HTTPStatus.OK)
async def get_singletimetariffinterval(
    tariff_id: int,
    site_id: int,
    rate_component_id: str,
    pricing_reading: PricingReadingType,
    tti_id: str,
    request: Request,
) -> XmlResponse:
    """Responds with a single TimeTariffInterval resource identified by the set of ID's.


    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        pricing_reading: Path parameter - the specific type of readings the prices should be associated with
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        tti_id: Path parameter, the target TimeTariffInterval id (should be a time in 24 hour HH:MM format)
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    try:
        tti = await TimeTariffIntervalManager.fetch_time_tariff_interval(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            tariff_id=tariff_id,
            site_id=site_id,
            rate_component_id=rate_component_id,
            time_tariff_interval=tti_id,
            pricing_type=pricing_reading,
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)

    if tti is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(tti)


@router.head(uri.ConsumptionTariffIntervalListUri)
@router.get(uri.ConsumptionTariffIntervalListUri, status_code=HTTPStatus.OK)
async def get_consumptiontariffintervallist(
    tariff_id: int,
    site_id: int,
    rate_component_id: str,
    pricing_reading: PricingReadingType,
    tti_id: str,
    sep2_price: int,
    request: Request,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a paginated list of ConsumptionTariffInterval belonging to specified parent ids.

    This endpoint is not necessary as it will always return a single price that is already encoded in the URI. It's
    implemented for the purposes of remaining sep2 compliant but clients to this implementation can avoid this call

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        pricing_reading: Path parameter - the specific type of readings the prices should be associated with
        tti_id: Path parameter, the target TimeTariffInterval id (should be a time in 24 hour HH:MM format)
        sep2_price: The price encoded in the URI from the parent TimeTariffInterval.ConsumptionTariffIntervalListLink
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
            aggregator_id=extract_aggregator_id(request),
            tariff_id=tariff_id,
            site_id=site_id,
            rate_component_id=rate_component_id,
            pricing_type=pricing_reading,
            time_tariff_interval=tti_id,
            sep2_price=sep2_price,
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")

    return XmlResponse(cti_list)


@router.head(uri.ConsumptionTariffIntervalUri)
@router.get(uri.ConsumptionTariffIntervalUri, status_code=HTTPStatus.OK)
async def get_singleconsumptiontariffinterval(
    tariff_id: int,
    site_id: int,
    rate_component_id: str,
    pricing_reading: PricingReadingType,
    tti_id: str,
    sep2_price: int,
    request: Request,
) -> XmlResponse:
    """Responds with a single ConsumptionTariffInterval resource.

    This endpoint is not necessary as it will always return a single price that is already encoded in the URI. It's
    implemented for the purposes of remaining sep2 compliant but clients to this implementation can avoid this call

    Args:
        tariff_id: Path parameter, the target TariffProfile's internal registration number.
        site_id: Path parameter - the site that the rates will be scoped to
        rate_component_id: Path parameter, the target RateComponent id (should be a date in YYYY-MM-DD format)
        pricing_reading: Path parameter - the specific type of readings the prices should be associated with
        tti_id: Path parameter, the target TimeTariffInterval id (should be a time in 24 hour HH:MM format)
        sep2_price: The price encoded in the URI from the parent TimeTariffInterval.ConsumptionTariffIntervalListLink
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """

    try:
        cti = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval(
            db.session,
            aggregator_id=extract_aggregator_id(request),
            tariff_id=tariff_id,
            site_id=site_id,
            rate_component_id=rate_component_id,
            pricing_type=pricing_reading,
            time_tariff_interval=tti_id,
            sep2_price=sep2_price,
        )
    except BadRequestError as ex:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=ex.message)
    except NotFoundError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found.")

    if cti is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(cti)
