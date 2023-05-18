from datetime import date, datetime, timezone
from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException, Request

MAX_LIMIT = 500
DEFAULT_LIMIT = 1
DEFAULT_START = 0
DEFAULT_DATETIME = datetime.min


def extract_aggregator_id(request: Request) -> int:
    """Fetches the aggregator id assigned to an incoming request (by the auth dependencies).

    raises a HTTPException if the id does not exist"""
    id = None if request.state is None else request.state.aggregator_id
    if id is None:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="aggregator_id has not been been extracted correctly by Envoy middleware.",
        )
    return id


def extract_limit_from_paging_param(limit: Optional[list[int]] = None) -> int:
    """Given a sep2 paging parameter called limit (as an int) - return the value, defaulting to DEFAULT_LIMIT if
    not specified"""
    if limit is None or len(limit) == 0:
        return DEFAULT_LIMIT

    limit_val = limit[0]
    if limit_val > MAX_LIMIT:
        return MAX_LIMIT

    return limit_val


def extract_start_from_paging_param(start: Optional[list[int]] = None) -> int:
    """Given a sep2 paging parameter called start (as an int) - return the value, defaulting to DEFAULT_START if
    not specified"""
    if start is None or len(start) == 0:
        return DEFAULT_START

    return start[0]


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
