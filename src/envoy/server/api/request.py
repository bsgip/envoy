
from datetime import datetime
from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException, Request


def extract_aggregator_id(request: Request) -> int:
    """Fetches the aggregator id assigned to an incoming request (by the auth dependencies).

    raises a HTTPException if the id does not exist"""
    id = None if request.state is None else request.state.aggregator_id
    if id is None:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                            detail="aggregator_id has not been been extracted correctly by Envoy middleware.")
    return id


def extract_limit_from_paging_param(limit: Optional[list[int]]) -> int:
    """Given a sep2 paging parameter called limit (as an int) - return the value, defaulting to 0 if not specified"""
    if limit is None or len(limit) == 0:
        return 1

    return limit[0]


def extract_start_from_paging_param(start: Optional[list[int]]) -> int:
    """Given a sep2 paging parameter called start (as an int) - return the value, defaulting to 0 if not specified"""
    if start is None or len(start) == 0:
        return 0

    return start[0]


def extract_datetime_from_paging_param(after: Optional[list[int]]) -> datetime:
    """Given a sep2 paging parameter called after (as an int) - return the equivalent
    datetime. If none is specified it will default to datetime.min"""
    if after is None or len(after) == 0:
        return datetime.min

    return datetime.fromtimestamp(after[0])
