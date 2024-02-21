import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.pub_sub import Subscription
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_request_params,
    extract_start_from_paging_param,
)
from envoy.server.api.response import LOCATION_HEADER_NAME, XmlRequest, XmlResponse
from envoy.server.exception import BadRequestError
from envoy.server.manager.subscription import SubscriptionManager
from envoy.server.mapper.common import generate_href

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head(uri.SubscriptionUri)
@router.get(
    uri.SubscriptionUri,
    status_code=HTTPStatus.OK,
)
async def get_subscription(
    request: Request,
    site_id: int,
    subscription_id: int,
) -> XmlResponse:
    """Responds with a specific subscription that exists underneath a site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        subscription_id: Path parameter, the target subscription ID
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    sub = await SubscriptionManager.fetch_subscription_by_id(
        db.session, extract_request_params(request), site_id=site_id, subscription_id=subscription_id
    )
    if sub is None:
        raise LoggedHttpException(logger, None, status_code=HTTPStatus.NOT_FOUND, detail="Not Found.")
    return XmlResponse(sub)


@router.head(uri.SubscriptionListUri)
@router.get(
    uri.SubscriptionListUri,
    status_code=HTTPStatus.OK,
)
async def get_subscriptions_for_site(
    request: Request,
    site_id: int,
    start: list[int] = Query([0], alias="s"),
    after: list[int] = Query([0], alias="a"),
    limit: list[int] = Query([1], alias="l"),
) -> XmlResponse:
    """Responds with a list of Subscriptions that exist for the specified site_id

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        start: list query parameter for the start index value. Default 0.
        after: list query parameter for lists with a datetime primary index. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 1.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    return XmlResponse(
        await SubscriptionManager.fetch_subscriptions_for_site(
            db.session,
            extract_request_params(request),
            site_id=site_id,
            start=extract_start_from_paging_param(start),
            after=extract_datetime_from_paging_param(after),
            limit=extract_limit_from_paging_param(limit),
        )
    )


@router.delete(
    uri.SubscriptionUri,
    status_code=HTTPStatus.OK,
)
async def delete_subscription(
    request: Request,
    site_id: int,
    subscription_id: int,
) -> Response:
    """Deletes a specific subscription that exists underneath a site

    Args:
        site_id: Path parameter, the target EndDevice's internal registration number.
        subscription_id: Path parameter, the target subscription ID
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """
    removed = await SubscriptionManager.delete_subscription_for_site(
        db.session, extract_request_params(request), site_id=site_id, subscription_id=subscription_id
    )
    return Response(status_code=HTTPStatus.NO_CONTENT if removed else HTTPStatus.NOT_FOUND)


@router.post(uri.SubscriptionListUri, status_code=HTTPStatus.CREATED)
async def create_subscription(
    request: Request,
    site_id: int,
    payload: Subscription = Depends(XmlRequest(Subscription)),
) -> Response:
    """An subscription resource is generated with a unique reg_no (registration number).
    This reg_no is used to set the resource path i.e.'/edev/1/sub/reg_no' which is
    sent to the client in the response 'Location' header.

    Args:
        response: fastapi.Response object.
        payload: The request payload/body object.

    Returns:
        fastapi.Response object.

    """
    rs_params = extract_request_params(request)
    try:
        sub_id = await SubscriptionManager.add_subscription_for_site(db.session, rs_params, payload, site_id)
        location_href = generate_href(uri.SubscriptionUri, rs_params, site_id=site_id, subscription_id=sub_id)
        return Response(status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: location_href})
    except BadRequestError as exc:
        raise LoggedHttpException(logger, exc, detail=exc.message, status_code=HTTPStatus.BAD_REQUEST)
