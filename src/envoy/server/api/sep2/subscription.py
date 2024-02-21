import logging
from http import HTTPStatus

from envoy_schema.server.schema import uri
from fastapi import APIRouter, Query, Request
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.api.request import (
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_request_params,
    extract_start_from_paging_param,
)
from envoy.server.api.response import XmlResponse
from envoy.server.manager.subscription import SubscriptionManager

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
