from datetime import date, datetime, timezone
from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException, Request

from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.request_scope import RawRequestClaims

MAX_LIMIT = 500
DEFAULT_LIMIT = 1
DEFAULT_START = 0
DEFAULT_DATETIME = datetime.min


def extract_request_claims(request: Request) -> RawRequestClaims:
    """Fetches the RawRequestClaims for the specified request..

    raises a HTTPException if the request is missing mandatory values"""
    if request.state is None:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Envoy middleware is not decorating incoming requests correctly.",
        )

    aggregator_id: Optional[int] = request.state.aggregator_id
    site_id: Optional[int] = request.state.site_id

    href_prefix: Optional[str] = getattr(request.state, "href_prefix", None)
    if not href_prefix:
        href_prefix = None

    source = request.state.source
    lfdi = request.state.lfdi
    sfdi = request.state.sfdi
    if not lfdi or not sfdi:  # disallow empty string and None
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"lfdi '{lfdi}' or sfdi '{sfdi}' have not been extracted correctly by Envoy middleware.",
        )

    return RawRequestClaims(
        source=source,
        aggregator_id_scope=aggregator_id,
        site_id_scope=site_id,
        lfdi=lfdi,
        sfdi=sfdi,
        href_prefix=href_prefix,
    )


def extract_default_doe(request: Request) -> Optional[DefaultDoeConfiguration]:
    """If the DefaultDoeDepends is enabled a DefaultDoeConfiguration will be returned for this request or None
    otherwise. This is a placeholder for static default DOE values"""
    if request.state is not None:
        return getattr(request.state, "default_doe", None)

    return None


def extract_limit_from_paging_param(limit: Optional[list[int]] = None) -> int:
    """Given a sep2 paging parameter called limit (as an int) - return the value, defaulting to DEFAULT_LIMIT if
    not specified.  Can raise HTTPException for invalid values"""
    if limit is None or len(limit) == 0:
        return DEFAULT_LIMIT

    limit_val = limit[0]
    if limit_val > MAX_LIMIT:
        return MAX_LIMIT

    if limit_val < 0:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "l parameters must be >= 0")

    return limit_val


def extract_start_from_paging_param(start: Optional[list[int]] = None) -> int:
    """Given a sep2 paging parameter called start (as an int) - return the value, defaulting to DEFAULT_START if
    not specified. Can raise HTTPException for invalid values"""
    if start is None or len(start) == 0:
        return DEFAULT_START

    start_val = start[0]
    if start_val < 0:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "s parameters must be >= 0")

    return start_val


def extract_datetime_from_paging_param(after: Optional[list[int]] = None) -> datetime:
    """Given a sep2 paging parameter called after (as an int) - return the equivalent
    datetime. If none is specified it will default to DEFAULT_DATETIME"""
    if after is None or len(after) == 0:
        return DEFAULT_DATETIME

    return datetime.fromtimestamp(after[0], tz=timezone.utc)


def extract_date_from_iso_string(iso_date: Optional[str] = None) -> Optional[date]:
    """Attempts to extract a date from a YYYY-MM-DD formatted string. This will be a strict
    extraction - any deviation from the format will result in None being returned"""
    if iso_date is None:
        return None

    if len(iso_date) != 10 or iso_date[4] != "-" or iso_date[7] != "-":
        return None

    try:
        return date.fromisoformat(iso_date)
    except ValueError:
        return None
